from wtforms import (
    Form,
    StringField,
    TextAreaField,
    BooleanField,
    IntegerField,
    validators,
)


def validate_api_key(form, api_key):
    """
    Validate API Key field.
    API Key must be present on new configuration creation.
    API Key is optional on updating existing configuraitons.
    """
    if form.id.data == 0 and len(api_key.data) == 0:
        raise validators.ValidationError()


class FormSubmission(Form):
    """
    Object to represent the html form submission aka incoming configuation data.
    This exists to apply data validation only.
    """

    id = IntegerField("id")
    ent_name = StringField("ent_name", [validators.DataRequired()])
    api_domain = StringField("api_domain", [validators.DataRequired()])
    proxy_addr = StringField("proxy_addr")
    proxy_username = StringField("proxy_username")
    proxy_password = StringField("proxy_password")
    api_key = TextAreaField("api_key", [validate_api_key])
    threat_enabled = BooleanField("threat_enabled")
    device_enabled = BooleanField("device_enabled")
    audit_enabled = BooleanField("audit_enabled")

    def __repr__(self) -> str:
        return f"""
FormSubmission(
    id:             {self.id.data}
    ent_name:       {self.ent_name.data}
    api_domain:     {self.api_domain.data}
    threat_enabled: {self.threat_enabled.data}
    device_enabled: {self.device_enabled.data}
    audit_enabled:  {self.audit_enabled.data}
)"""
