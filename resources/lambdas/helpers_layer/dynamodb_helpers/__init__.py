import boto3
import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from log_helpers import ensure_logger


class ShopDoesNotExist(Exception):
    pass


class DynamodbTestOrdersData:
    def __init__(self, table_name: str, dynamodb_resource=None, logger=None):
        self.table_name = table_name
        if dynamodb_resource is not None:
            self.ddb = dynamodb_resource
        else:
            self.ddb = boto3.resource("dynamodb")
        self.logger = ensure_logger(logger)
        self.table = self._create_table()

    def _create_table(self):
        # Check if the table already exists
        try:
            table = self.ddb.Table(self.table_name)
            self.logger.info(f"table status : {table.table_status}")
            return table
        except self.ddb.meta.client.exceptions.ResourceNotFoundException:
            table = self.ddb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "PK", "AttributeType": "S"},
                    {"AttributeName": "SK", "AttributeType": "S"},
                    {"AttributeName": "GSI1-PK", "AttributeType": "S"},
                    {"AttributeName": "GSI1-SK", "AttributeType": "S"},
                    {"AttributeName": "GSI2-PK", "AttributeType": "S"},
                    {"AttributeName": "GSI2-SK", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "GSI1",
                        "KeySchema": [
                            {"AttributeName": "GSI1-PK", "KeyType": "HASH"},
                            {"AttributeName": "GSI1-SK", "KeyType": "RANGE"},
                        ],
                        "Projection": {
                            "ProjectionType": "ALL",
                        },
                    },
                    {
                        "IndexName": "GSI2",
                        "KeySchema": [
                            {"AttributeName": "GSI2-PK", "KeyType": "HASH"},
                            {"AttributeName": "GSI2-SK", "KeyType": "RANGE"},
                        ],
                        "Projection": {
                            "ProjectionType": "ALL",
                        },
                    },
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            self.logger.info(f"Table {self.table_name} is being created")
            # Wait for the table to be created
            waiter = boto3.client("dynamodb").get_waiter("table_exists")
            waiter.wait(TableName=self.table_name)
            self.logger.info(f"Table {self.table_name} has been created")
            return table

    @staticmethod
    def create_shop_data(shop_id: str) -> dict:
        return {
            "PK": f"s#{shop_id}",
            "SK": f"s#{shop_id}",
            "entityType": "shop",
            "name": f"Shop {shop_id}",
            "phoneNumber": "077" + "".join(random.choices(string.digits, k=7)),
            "address": f'{{"street": {{"S": "Dammweg {random.randint(1,10)}"}}, "city": {{"S": "Bern"}}, "postalCode": {{"N": "3013"}}',
        }

    def prefill_table_with_testdata(self, test_customers: list[dict] = None) -> None:
        # Generate shops and products test data
        shop_data = []
        for shop_id in range(1, 3):
            new_shop = self.create_shop_data(f"000{shop_id}")
            shop_data.append(new_shop)
            pk = new_shop["PK"]

            for order_item_nb in range(1, 3):
                product_id = f"00{shop_id}{order_item_nb}"
                shop_data.append(
                    {
                        "PK": pk,
                        "SK": f"p#{product_id}",
                        "entityType": "product",
                        "name": "".join(random.choices(string.ascii_uppercase, k=1))
                        + "".join(random.choices(string.ascii_lowercase, k=4)),
                        "description": "".join(
                            random.choices(string.ascii_letters, k=10)
                        ),
                        "price": int(product_id) * 10,
                    }
                )
        self.logger.info("Writing shops and products items to the table")
        try:
            with self.table.batch_writer() as batch:
                for item in shop_data:
                    batch.put_item(Item=item)
        except Exception as e:
            self.logger.error(
                f"Error while writing the shops and products data to the table: {e}"
            )
            raise e
        self.logger.info(
            "Test shops and products items data have been written to the table"
        )

        for item in shop_data:
            if item["entityType"] != "shop":
                continue
            shop_id = item["SK"].replace("s#", "")
            self.regenerate_shop_token(shop_id=shop_id)

        # If there is test_customers then add a visitor customer
        # If not crete 2 visitor customers
        if test_customers is None:
            test_customers = []
            for i in range(1, 3):
                test_customers.append(
                    {
                        "username": f"Visitor Customer #{i}",
                        "dynamodb_key": f"v#{uuid.uuid4()}",
                        "phone_number": "077000" + f"{i}" * 4,
                    }
                )
        else:
            test_customers.append(
                {
                    "username": "Visitor Customer #1",
                    "dynamodb_key": f"v#{uuid.uuid4()}",
                    "phone_number": "0770001111",
                }
            )
        # For each customer generate 1 orders data in every shop
        order_data = []
        for i, customer in enumerate(test_customers):
            self.logger.info(
                f"Generating test data for customer {customer['username']}"
            )
            for order_nb in range(1, 3):
                # Prepare data
                order_id = order_nb + i * 2
                order_pk = "o#" + f"{order_id}" * 4
                # For each customer the first order is placed in the first shop, second order in the second shop...
                shop_id = order_nb
                # Generate the order date as the current date minus the order_id days
                order_date = datetime.now(timezone.utc) - timedelta(days=order_id)
                order_date_str = order_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                total_amount = 0
                # Generate the order product data. Each order has 1 product ordered
                # The first customer orders the first product of every shop, the second customer the second product of every shop...
                order_item_nb = i + 1
                product_id = f"00{shop_id}{order_item_nb}"
                # Get the product name and price from the table
                product_data = self.get_product_data_by_number(shop_id, order_item_nb)
                order_data.append(
                    {
                        "PK": order_pk,
                        "SK": f"p#{product_id}",
                        "entityType": "orderItem",
                        "quantity": order_item_nb,
                        "name": product_data["name"],
                        "price": product_data["price"],
                    }
                )
                total_amount += product_data["price"] * order_item_nb
                # Generate the order data
                order_data.append(
                    {
                        "PK": order_pk,
                        "SK": order_pk,
                        "entityType": "order",
                        "GSI1-PK": f"s#000{shop_id}",
                        "GSI1-SK": order_date_str,
                        "GSI2-PK": customer["dynamodb_key"],
                        "GSI2-SK": order_date_str,
                        "phoneNumber": customer["phone_number"],
                        "name": customer["username"],
                        "date": order_date_str,
                        "status": "PENDING",
                        "amount": total_amount,
                    }
                )
        self.logger.info("Writing order items to the table")
        try:
            with self.table.batch_writer() as batch:
                for item in order_data:
                    batch.put_item(Item=item)
        except Exception as e:
            self.logger.error(f"Error while writing the orders data to the table: {e}")
            raise e
        self.logger.info("Test order items data have been written to the table")

    def get_product_data_by_number(self, shop_nb: int, product_nb: int) -> dict:
        """Get the product data by the shop and product numbers (e.g. shop 1 and product 1)"""
        shop_id = f"s#000{shop_nb}"
        product_id = f"p#00{shop_nb}{product_nb}"
        get_response = self.table.get_item(Key={"PK": shop_id, "SK": product_id})
        product_data = get_response.get("Item", {})
        if not product_data:
            self.logger.warning(
                f"Product data not found for shop {shop_nb} and product {product_nb}"
            )
        return product_data

    def get_product_data_by_key(self, shop_key: str, product_key: str) -> dict:
        """Get the product data by the shop and product Key (e.g. shop s#0001 and product p#0011)"""
        get_response = self.table.get_item(Key={"PK": shop_key, "SK": product_key})
        product_data = get_response.get("Item", {})
        if not product_data:
            self.logger.warning(
                f"Product data not found for shop {shop_key} and product {product_key}"
            )
        return product_data

    def regenerate_shop_token(self, shop_id: str) -> str:
        # Generate random token: 3 uppercase letters + 3 digits
        letters = "".join(random.choices(string.ascii_uppercase, k=3))
        digits = "".join(random.choices(string.digits, k=3))
        new_token = letters + digits
        # Update the item in DynamoDB
        try:
            self.table.update_item(
                Key={"PK": f"s#{shop_id}", "SK": f"s#{shop_id}"},
                UpdateExpression="SET shopToken = :token",
                ConditionExpression="attribute_exists(PK)",  # Ensure the PK exists
                ExpressionAttributeValues={":token": new_token},
                ReturnValues="UPDATED_NEW",
            )
            return new_token
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Handle the case where the item does not exist
                raise ShopDoesNotExist(f"Shop with ID {shop_id} does not exist.")
            else:
                # Re-raise other unexpected exceptions
                raise

    def put_new_order(
        self,
        shop_id: int,
        customer_key: str,
        phone_number: str,
        customer_name: str,
        items: list[dict],
    ) -> str:
        """Put a new order in the databasewith the given data.
        The order is composed of the shop ID, the phone number of the customer and the list of product items.
        Items must be a list of dictionaries with the following keys: productId, quantity
        """
        order_id = self._generate_unique_request_id()
        order_key = f"o#{order_id}"
        order_timestamp = datetime.now(timezone.utc).isoformat()
        shop_key = f"s#{shop_id}"
        # Get the products data and compute the order amount
        total_amount = 0
        order_data = []
        for item in items:
            product_key = f"p#{item['productId']}"
            product_data = self.get_product_data_by_key(shop_key, product_key)
            order_data.append(
                {
                    "PK": order_key,
                    "SK": product_key,
                    "entityType": "orderItem",
                    "quantity": item["quantity"],
                    "name": product_data["name"],
                    "price": product_data["price"],
                }
            )
            total_amount += product_data["price"] * item["quantity"]
        order_data.append(
            {
                "PK": order_key,
                "SK": order_key,
                "entityType": "order",
                "GSI1-PK": shop_key,
                "GSI1-SK": order_timestamp,
                "GSI2-PK": customer_key,
                "GSI2-SK": order_timestamp,
                "phoneNumber": phone_number,
                "name": customer_name,
                "date": order_timestamp,
                "status": "PENDING",
                "amount": total_amount,
            }
        )
        self.logger.info(f"Writing all items to the table for new order {order_key}")
        try:
            with self.table.batch_writer() as batch:
                for item in order_data:
                    batch.put_item(Item=item)
        except Exception as e:
            self.logger.error(f"Error while writing the orders data to the table: {e}")
            raise e
        self.logger.info(f"Items have been written to the table for order {order_key}")
        return order_id

    @staticmethod
    def _abstract_order_item_schema(order: dict) -> dict:
        """Abstract the order item schema to the expected schema"""
        # To abstract the table schema
        # Rename the PK to orderId and drop the SK
        # Rename the GSI2-PK key to customerId and drop the GSI2-SK
        # Remove the entityType since we know we are returning orders here
        # Rename the GSI1-PK key to shopId and drop the GSI1-SK
        return {
            "orderId": order["PK"].split("#")[-1],
            "shopId": order["GSI1-PK"].split("#")[-1],
            "customerId": order["GSI2-PK"].split("#")[-1],
            **{
                k: v
                for k, v in order.items()
                if k
                not in {
                    "PK",
                    "SK",
                    "GSI1-PK",
                    "GSI1-SK",
                    "GSI2-PK",
                    "GSI2-SK",
                    "entityType",
                }
            },
        }

    def get_order_data(self, order_id: str) -> dict:
        """Get the order data from the database by the order ID (e.g. 1234)"""
        get_response = self.table.get_item(
            Key={"PK": f"o#{order_id}", "SK": f"o#{order_id}"}
        )
        order_data = get_response.get("Item", {})
        # Abstract the table schema
        order_data = self._abstract_order_item_schema(order=order_data)
        if not order_data:
            self.logger.warning(f"Order data not found for order {order_id}")
        return order_data

    def list_products_by_shop_id(self, shop_id: str) -> list:
        """Get the products from the database by the shop ID (e.g. 1234)"""
        get_response = self.table.query(
            KeyConditionExpression=Key("PK").eq(f"s#{shop_id}")
            & Key("SK").begins_with("p#")
        )
        products_list = get_response.get("Items", [])
        # To abstract the table schema
        # Rename the PK key of shopId
        # Rename the SK key to productId
        # Remove the entityType since we know we are returning products here
        for product in products_list:
            product["shopId"] = product.pop("PK").split("#")[-1]
            product["productId"] = product.pop("SK").split("#")[-1]
            product.pop("entityType", None)
        if not products_list:
            self.logger.warning(f"Products not found for shop {shop_id}")
        return products_list

    def list_orders_by_shop_id(self, shop_id: str) -> list:
        """Get the orders from the database by the shop ID (e.g. 1234)"""
        query_response = self.table.query(
            IndexName="GSI1", KeyConditionExpression=Key("GSI1-PK").eq(f"s#{shop_id}")
        )
        orders_list = query_response.get("Items", [])
        # Abstract the table schema
        orders_list = [self._abstract_order_item_schema(order) for order in orders_list]
        if not orders_list:
            self.logger.warning(f"Orders not found for shop {shop_id}")
        return orders_list

    def get_total_amount_by_shop_id(self, shop_id: str) -> Decimal:
        """Get the total amount from the database by the shop ID (e.g. 1234)"""
        query_response = self.table.query(
            IndexName="GSI1", KeyConditionExpression=Key("GSI1-PK").eq(f"s#{shop_id}")
        )
        total_amount = Decimal(0)
        for item in query_response["Items"]:
            total_amount = total_amount + item["amount"]
        return total_amount

    def list_shops(self) -> list[dict]:
        """Get the list of shops from the database"""
        shops = []
        scan_kwargs = {"FilterExpression": Attr("entityType").eq("shop")}
        while True:
            scan_response = self.table.scan(**scan_kwargs)
            shops.extend(scan_response.get("Items", []))
            if "LastEvaluatedKey" not in scan_response:
                break
            scan_kwargs["ExclusiveStartKey"] = scan_response["LastEvaluatedKey"]
        for shop in shops:
            shop["shopId"] = shop.pop("PK").split("#")[-1]
            shop.pop("SK", None)
        return shops

    def get_shop_by_id(self, shop_id: str) -> dict:
        get_item_response = self.table.get_item(
            Key={"PK": f"s#{shop_id}", "SK": f"s#{shop_id}"}
        )
        shop_data = get_item_response.get("Item")
        if shop_data:
            # To abstract the table schema
            # Rename the PK key of shopId and remove the SK
            # Remove the entityType since we know we are returning products here
            shop_data["shopId"] = shop_data.pop("PK").split("#")[-1]
            for key in ["SK", "entityType"]:
                shop_data.pop(key, None)
        return shop_data

    def _generate_unique_request_id(
        self, id_length: int = 4, max_attempts: int = 10
    ) -> string:
        """Generate an order ID ID and check if it is already used or not.
        If already used it is generating a new one.

        :param id_length: The length of the ID.
                            The default value is 10 charachters.
        :param max_attempts: The maximum number of attempts to generate a new ID before failing
                                The default value is 10 attempts.

        :return: string: The unique order ID ot the "ERROR" value if no unique ID
                    could be generated in the maximum number of attempts
        """
        for i in range(max_attempts):
            new_request_id = "".join(random.choices(string.digits, k=id_length))
            get_item_response = self.table.get_item(
                Key={"PK": f"o#{new_request_id}", "SK": f"o#{new_request_id}"}
            )
            if "Item" not in get_item_response:
                return new_request_id
        return "ERROR"
