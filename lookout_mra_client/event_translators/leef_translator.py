"""
Module containing attribute mapping for MRA events in LEEF format.
LEEF format follows the below pattern:

<timestamp> <logId> LEEF:<version>|<vendor>|<product>|<version>|<eventId>|<attribute1>=<value1><fieldSep><attribute2>=<value2>...

We use the following values while building the LEEF header:
- logId: Defined against 'LOG_SOURCE_IDENTIFIER' in config.json
- vendor: Lookout
- product: MRAv1 Client or MRAv2 Client
- version: 0.2 for MRAv1 and 2.0 for MRAv2
- fieldSep: Tab character ("\t")

`Event Category` is mapped to the `cat` attribute in the QRadar console.

"""

from datetime import datetime
from .utilities import transform_event
from .mra_v1_leef_mapping import MRA_V1_LEEF_MAPPING
from .mra_v2_leef_mapping import MRA_V2_LEEF_MAPPING

LEEF_FIELD_SEP = "\t"
TIMESTAMP_FMT = "%b %d %H:%M:%S"


class LeefTranslator:
    def __init__(self, mra_v2: bool = False):
        self.mra_v2 = mra_v2

    def formatEvent(self, event: dict) -> str:
        if self.mra_v2:
            return self.__format_mra_v2_event(event)
        else:
            return self.__format_mra_v1_event(event)

    def __format_mra_v2_event(self, event: dict) -> str:
        event_type = event.get("type", "UNKNOWN")
        event_cat = event.get("change_type", "UNKNOWN")
        cat_mapping = (("change_type", "cat"),)

        # Use details.classifications for a more granual categorization of threat events
        if event_type == "THREAT":
            threat = event.get("threat") or {}
            classifications = threat.get("classifications") or []
            event_cat = classifications[0] if classifications else "UNKNOWN"
            cat_mapping = (("threat.classifications", "cat"),)
        elif event_type == "DEVICE":
            # can contain: activationStatus, protectionStatus, securityStatus
            device = event.get("device", {})
            device_status = device.get("status", {})
            # ACTIVATED, DEACTIVATED, PENDING, DELETED
            activation_status = device_status.get("activation_status", "UNKNOWN")

            if activation_status in ("DELETED", "DEACTIVATED", "PENDING"):
                event_cat = activation_status
                cat_mapping = (("device.status.activation_status", "cat"),)
            elif "security_status" in device_status:
                security_status = device_status["security_status"]

                event_cat = activation_status + "_" + security_status
                cat_mapping = (
                    (
                        "device.status.activation_status",
                        "device.status.security_status",
                        "cat",
                        lambda n1, n2: n1 + "_" + n2,
                    ),
                )
            else:
                event_cat = event.get("change_type", "UNKNOWN")
                cat_mapping = (("change_type", "cat"),)

        elif event_type == "AUDIT":
            audit = event.get("audit", {})
            event_cat = audit.get("type", "UNKNOWN")
            cat_mapping = (("audit.type", "cat"),)

        mapping = cat_mapping + MRA_V2_LEEF_MAPPING

        timestamp = datetime.now().strftime(TIMESTAMP_FMT)
        logId = event.get("qradarLogSourceIdentifier", "LOOKOUT")
        leef_header = (
            f"{timestamp} {logId} LEEF:2.0|Lookout|MRAv2 Client|2.0|{event_type},{event_cat}|"
        )

        mapped_event = transform_event(mapping, event)
        event_attr = LEEF_FIELD_SEP.join(f"{key}={val}" for key, val in mapped_event.items())

        return leef_header + event_attr

    def __format_mra_v1_event(self, event: dict) -> str:
        event_type = event.get("type", "UNKNOWN")
        details = event.get("details", {})
        event_cat = details.get("type", "UNKNOWN")
        cat_mapping = (("details.type", "cat"),)

        # Use details.classifications for a more granual categorization of threat events
        if event_type == "THREAT":
            classifications = details.get("classifications", ["UNKNOWN"])
            event_cat = classifications[0] if classifications else "UNKNOWN"
            cat_mapping = (("details.classifications", "cat"),)
        elif event_type == "DEVICE":
            # can contain: activationStatus, protectionStatus, securityStatus
            updated_details = event.get("updatedDetails", {})
            # ACTIVATED, DEACTIVATED, PENDING, DELETED
            activation_status = details.get("activationStatus", "UNKNOWN")

            if activation_status in ("DELETED", "DEACTIVATED", "PENDING"):
                event_cat = activation_status
                cat_mapping = (("details.activationStatus", "cat"),)
            elif "securityStatus" in updated_details:
                security_status = details.get("securityStatus", "UNKNOWN")

                if "activationStatus" in updated_details:
                    event_cat = activation_status + "_" + security_status
                    cat_mapping = (
                        (
                            "details.activationStatus",
                            "details.securityStatus",
                            "cat",
                            lambda n1, n2: n1 + "_" + n2,
                        ),
                    )
                else:
                    event_cat = security_status
                    cat_mapping = (("details.securityStatus", "cat"),)

        mapping = cat_mapping + MRA_V1_LEEF_MAPPING

        timestamp = datetime.now().strftime(TIMESTAMP_FMT)
        logId = event.get("qradarLogSourceIdentifier", "LOOKOUT")
        leef_header = (
            f"{timestamp} {logId} LEEF:1.0|Lookout|SIEM Client|0.2|{event_type},{event_cat}|"
        )

        mapped_event = transform_event(mapping, event)
        event_attr = LEEF_FIELD_SEP.join(f"{key}={val}" for key, val in mapped_event.items())

        return leef_header + event_attr
