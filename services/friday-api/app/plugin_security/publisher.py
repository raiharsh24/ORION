from datetime import datetime, timezone
from typing import Optional

from app.plugin_security.base import (
    PublisherInfo, TrustLevel, CertificateInfo,
)


class PublisherRegistry:
    def __init__(self):
        self._publishers: dict[str, PublisherInfo] = {}

    def register(self, publisher_id: str, name: str,
                 email: str = "", website: str = "",
                 trust_level: TrustLevel = TrustLevel.UNTRUSTED) -> PublisherInfo:
        now = datetime.now(timezone.utc)
        info = PublisherInfo(
            publisher_id=publisher_id,
            name=name,
            email=email,
            website=website,
            trust_level=trust_level,
            created_at=now,
            updated_at=now,
        )
        self._publishers[publisher_id] = info
        return info

    def get(self, publisher_id: str) -> Optional[PublisherInfo]:
        return self._publishers.get(publisher_id)

    def set_trust_level(self, publisher_id: str,
                        trust_level: TrustLevel) -> bool:
        pub = self._publishers.get(publisher_id)
        if pub is None:
            return False
        pub.trust_level = trust_level
        pub.updated_at = datetime.now(timezone.utc)
        return True

    def add_certificate(self, publisher_id: str,
                        cert: CertificateInfo) -> bool:
        pub = self._publishers.get(publisher_id)
        if pub is None:
            return False
        pub.certificates.append(cert)
        pub.updated_at = datetime.now(timezone.utc)
        return True

    def is_trusted(self, publisher_id: str) -> bool:
        pub = self._publishers.get(publisher_id)
        if pub is None:
            return False
        return pub.is_trusted

    def get_trusted_publishers(self) -> list[PublisherInfo]:
        return [p for p in self._publishers.values() if p.is_trusted]

    def get_revoked_publishers(self) -> list[PublisherInfo]:
        return [p for p in self._publishers.values()
                if p.trust_level == TrustLevel.UNTRUSTED]

    def get_all(self) -> list[PublisherInfo]:
        return list(self._publishers.values())

    def count(self) -> int:
        return len(self._publishers)

    def trust(self, publisher_id: str) -> bool:
        return self.set_trust_level(publisher_id, TrustLevel.VERIFIED)

    def revoke_trust(self, publisher_id: str) -> bool:
        return self.set_trust_level(publisher_id, TrustLevel.UNTRUSTED)

    def remove(self, publisher_id: str) -> bool:
        if publisher_id in self._publishers:
            del self._publishers[publisher_id]
            return True
        return False
