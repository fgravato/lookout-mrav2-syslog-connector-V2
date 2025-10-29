import ast, logging
from datetime import datetime
from types import ModuleType

from peewee import *
from furl import furl

from ..lookout_logger import LOGGER_NAME
from .base_model import BaseModel
from .form_submission import FormSubmission


class Configuration(BaseModel):
    """
    Python object to hold/mutate configuration from sql.
    """

    ent_name = CharField()
    api_domain = CharField()
    threat_enabled = BooleanField()
    device_enabled = BooleanField()
    audit_enabled = BooleanField()
    stream_position = CharField()
    start_time = DateTimeField()
    fetch_count = IntegerField()
    fetched_at = DateTimeField(null=True)
    proxy_addr = CharField()
    proxy_username = CharField()

    api_key = ""
    proxy_password = ""

    class Meta:
        table_name = "Configuration"

    def __repr__(self) -> str:
        return f"""
Configuration(
    id:              {self.id}
    ent_name:        {self.ent_name}
    api_domain:      {self.api_domain}
    threat_enabled:  {self.threat_enabled}
    device_enabled:  {self.device_enabled}
    audit_enabled:   {self.audit_enabled}
    stream_position: {self.stream_position}
    start_time:      {self.start_time}
    fetch_count:     {self.fetch_count}
    fetched_at:      {self.fetched_at}
    proxy_addr:      {self.proxy_addr}
    proxy_username:  {self.proxy_username}
)"""

    def __eq__(self, other) -> bool:
        if not isinstance(other, Configuration):
            return False

        return (
            self.ent_name == other.ent_name
            and self.api_domain == other.api_domain
            and self.threat_enabled == other.threat_enabled
            and self.device_enabled == other.device_enabled
            and self.audit_enabled == other.audit_enabled
            and self.stream_position == other.stream_position
            and self.start_time == other.start_time
            and self.fetch_count == other.fetch_count
            and self.fetched_at == other.fetched_at
            and self.proxy_addr == other.proxy_addr
            and self.proxy_username == other.proxy_username
        )

    # NOTE: type hints for returning a class object from a class method is not yet supported
    @classmethod
    def get_configuration_by_id(
        cls, id: int, load_secrets: bool = False, secrets_manager: ModuleType = None
    ):
        """
        Retrieve configuration from db based on given id. Only load secrets
        if `load_secrets` is set.
        """
        logger = logging.getLogger(LOGGER_NAME)

        try:
            config = Configuration.get(Configuration.id == id)
        except DoesNotExist as e:
            logger.error("Failed to get configuration '{}' from db: {}".format(id, e))
            return None

        if load_secrets:
            if secrets_manager is None:
                msg = "Cannot load secrets with no secrets manager provided"
                logger.error(msg)
                raise ValueError(msg)
            try:
                enc = secrets_manager.Encryption({"name": config.id, "user": "configuration"})
                secrets = ast.literal_eval(enc.decrypt())

                config.api_key = secrets["api_key"]
                config.proxy_password = secrets["proxy_password"]
            except secrets_manager.EncryptionError as e:
                logger.error("Failed to retrieve secrets: {}".format(e))
                return None
        return config

    @classmethod
    def update_or_create(cls, form: FormSubmission, secrets_manager: ModuleType) -> str:
        """
        Update the configuration if it exists, else create a new one.
        Also update the encrypted secrets using qpylib.encdec
        """
        logger = logging.getLogger(LOGGER_NAME)
        if form.id.data == 0:
            return cls.__create_configuration(logger, form, secrets_manager)
        else:
            return cls.__update_configuration(logger, form, secrets_manager)

    @classmethod
    def __create_configuration(
        cls, logger: logging.Logger, form: FormSubmission, secrets_manager: ModuleType
    ) -> str:
        """
        Create a brand new configuration in the db and store secrets in
        encrypted storage.
        """
        secrets = {
            "api_key": form.api_key.data,
            "proxy_password": form.proxy_password.data,
        }

        try:
            config = Configuration.create(
                ent_name=form.ent_name.data,
                api_domain=form.api_domain.data,
                threat_enabled=form.threat_enabled.data,
                device_enabled=form.device_enabled.data,
                audit_enabled=form.audit_enabled.data,
                stream_position="",
                start_time=datetime.today(),
                fetch_count=0,
                fetched_at=None,
                proxy_addr=form.proxy_addr.data,
                proxy_username=form.proxy_username.data,
            )
            config.save()
        except Exception as e:
            msg = "Failed to create configuration '{}' in db: {}".format(form.ent_name.data, e)
            logger.error(msg)
            return msg
        try:
            enc = secrets_manager.Encryption({"name": config.id, "user": "configuration"})
            enc.encrypt(str(secrets))
        except secrets_manager.EncryptionError as e:
            msg = "Failed to create secrets, nuking configuration: {}".format(e)
            logger.error(msg)
            config.delete_instance()
            return msg
        return "Configuration saved successfully!"

    @classmethod
    def __update_configuration(
        cls, logger: logging.Logger, form: FormSubmission, secrets_manager: ModuleType
    ) -> str:
        """
        Update an existing configuration in the db and only update
        secrets if they differ from stored secrets and are not blank.
        """
        config = cls.get_configuration_by_id(1, load_secrets=True, secrets_manager=secrets_manager)
        if config is None:
            return "Failed to update configuration from db!"

        secrets = {"api_key": config.api_key, "proxy_password": config.proxy_password}

        if len(form.api_key.data) > 0 and form.api_key.data != config.api_key:
            secrets["api_key"] = form.api_key.data
        if len(form.proxy_password.data) > 0 and form.proxy_password.data != config.proxy_password:
            secrets["proxy_password"] = form.proxy_password.data

        try:
            config.ent_name = form.ent_name.data
            config.api_domain = form.api_domain.data
            config.threat_enabled = form.threat_enabled.data
            config.device_enabled = form.device_enabled.data
            config.audit_enabled = form.audit_enabled.data
            config.proxy_addr = form.proxy_addr.data
            config.proxy_username = form.proxy_username.data
            if secrets["api_key"] != config.api_key:
                config.start_time = datetime.today()
            config.save()
        except Exception as e:
            msg = "Failed to update configuration '{}' to db: {}".format(config.id, e)
            logger.error(msg)
            return msg
        try:
            enc = secrets_manager.Encryption({"name": config.id, "user": "configuration"})
            enc.encrypt(str(secrets))
        except secrets_manager.EncryptionError as e:
            msg = "Failed to update configuration secrets: {}".format(e)
            logger.error(msg)
            return msg
        return "Configuration updated successfully!"


def format_proxy(config: Configuration) -> dict:
    """
    Helper function that formats a configuration's proxy info
    in the dict format required by requests library.
    """
    proxies = {}

    url = furl(config.proxy_addr)
    if config.proxy_username:
        url.username = config.proxy_username
        if config.proxy_password:
            url.password = config.proxy_password

    if url.scheme and url.host and url.port:
        proxies[url.scheme] = url.tostr()

    return proxies


def event_type_display(config: Configuration) -> str:
    """
    Helper function for display/formatting event types based
    on a given Configuration object
    """
    types = []
    if config is None:
        return ""
    if config.threat_enabled:
        types.append("THREAT")
    if config.device_enabled:
        types.append("DEVICE")
    if config.audit_enabled:
        types.append("AUDIT")
    return ",".join(types)
