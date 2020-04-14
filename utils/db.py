
import boto3
from boto3.dynamodb.conditions import Key, Attr

from utils.utility import module_logger, stream_logger


class TableError(Exception):
    pass


class Table:
    def __init__(self, table_name, bot=None):
        if bot:
            self.logger = module_logger(bot.name, 'dynamodb')
        else:
            self.logger = stream_logger('dynamodb')
        self.name = table_name
        self.resource = boto3.resource('dynamodb', region_name='us-east-2')
        self.table = self.resource.Table(table_name)
        self.primary_key = self.table.key_schema[0]['AttributeName']
        self.sort_key = self.table.key_schema[1]['AttributeName']
        self.logger.debug(f"Dynamodb table initialized. ({table_name})")

    def put(self, data, key_data=None):
        self.logger.debug(f"Writing to table: {self.name} ({key_data if key_data else ''}) - {data}")
        if key_data is not None:
            for i, key in enumerate(key_data):
                data[[self.primary_key, self.sort_key][i]] = key
        # try:
        self.table.put_item(Item=data)
        self.logger.debug("Successfully wrote to table.")
        return True
        # except Exception as e:
        #     self.logger.error(f"Error writing to table {self.name}:", exc_info=True)
        #     return None

    def get(self, key_data):
        self.logger.debug(f"Reading table: {self.name} ({key_data})")
        # try:
        keys = dict()
        if len(key_data) != 2:
            return None
        for i, key in enumerate(key_data):
            keys[[self.primary_key, self.sort_key][i]] = key
        response = self.table.get_item(Key=keys)
        item = response['Item']
        self.logger.debug("Successfully read table.")
        return item
        # except Exception as e:
        #     self.logger.debug(f"Error reading table {self.name}:", exc_info=True)
        #     return None

    def read(self, sort_key):
        self.logger.debug(f"Bulk reading table: {self.name} - {sort_key}.")
        # try:
        response = self.table.scan(FilterExpression=Key(self.sort_key).eq(sort_key))
        items = response['Items']
        self.logger.debug(f"Successfully bulk read table {self.name} - {sort_key}")
        return items
        # except Exception as e:
        #     self.logger.debug(f"Error reading table {self.name}:", exc_info=True)
        #     return None

    def read_to_dict(self, sort_key):
        response = self.read(sort_key)
        data = dict()
        key_schema = [self.primary_key, self.sort_key]
        for item in response:
            data[int(item.pop(key_schema[0]))] = item
            item.pop(key_schema[1])
        return data

    def write(self, items, sort_key=None):
        self.logger.debug(f"Reading table: {self.name}")
        with self.table.batch_writer() as batch:
            for item in items:
                if sort_key:
                    item[self.sort_key] = sort_key
                batch.put_item(Item=item)

    def write_from_dict(self, data, sort_key):
        items = list()
        for key, value in data.items():
            value[self.primary_key] = key
            value[self.sort_key] = sort_key
            items.append(value)
        self.write(items)


if __name__ == "__main__":
    table = Table("Bulbe")
    x = table.read_to_dict('config')
    print(x)
