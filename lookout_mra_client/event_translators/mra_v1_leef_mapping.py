MRA_V1_LEEF_MAPPING = (
    ("entName", "lookoutEntName"),
    ("id", "lookoutId"),
    ("eventTime", "lookoutEventTime"),
    ("changeType", "lookoutChangeType"),
    ("details.type", "lookoutEventType"),
    # Threat
    ("details.id", "lookoutThreatId"),
    ("details.action", "lookoutAction"),
    ("details.severity", "lookoutSeverity"),
    ("details.classifications", "lookoutClassifications"),
    ("details.url", "lookoutUrl"),
    # Threat - Network
    ("details.ssid", "lookoutSSID"),
    ("details.macAddress", "lookoutMacAddress"),
    ("details.proxyProtocol", "lookoutProxyProtocol"),
    ("details.proxyPort", "lookoutProxyPort"),
    ("details.proxyAddress", "lookoutProxyAddress"),
    ("details.vpnLocalAddress", "lookoutVpnLocalAddress"),
    (
        "details.vpnPresent",
        "lookoutVpnPresent",
        lambda vpnPresent: 1 if vpnPresent else 0,
    ),
    # Threat - Application/File
    ("details.dnsIpAddresses", "lookoutDnsIpAddresses"),
    (
        "details.applicationName",
        "details.packageName",
        "lookoutAppProcessDetails",
        lambda n1, n2: n1 + "," + n2,
    ),
    ("details.fileName", "lookoutAppFileName"),
    ("details.path", "lookoutAppFilePath"),
    # Threat - Configuration
    ("details.trustedSigningIdentity", "lookoutTrustedSigningIdentity"),
    # Threat - OS
    ("details.osVersion", "lookoutOSVersion"),
    ("details.pcpReportingReason", "lookoutPcpReportingReason"),
    ("details.pcpDeviceResponse", "lookoutPcpDeviceResponse"),
    # Device
    ("details.activationStatus", "lookoutActivationStatus"),
    ("details.protectionStatus", "lookoutProtectionStatus"),
    ("details.securityStatus", "lookoutSecurityStatus"),
    ("updatedDetails", "lookoutUpdatedDetails"),
    # Device - Target
    ("target.id", "lookoutTargetId"),
    ("target.externalId", "lookoutTargetExternalId"),
    ("target.platform", "lookoutTargetPlatform"),
    ("target.emailAddress", "lookoutUser"),
    ("target.IMEI", "lookoutTargetIMEI"),
    # Audit
    ("actor.type", "lookoutActorType"),
    ("actor.id", "lookoutActorId"),
    ("details.attributeChanges", "lookoutAttributeChanges"),
)
