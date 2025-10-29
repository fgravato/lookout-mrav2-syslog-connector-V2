from peewee import Model, DatabaseProxy

db_proxy = DatabaseProxy()


class BaseModel(Model):
    class Meta:
        database = db_proxy
