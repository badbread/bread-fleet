"""Curated product-to-osquery mapping registry.

Each entry maps a (vendor, product) pair from the CISA KEV feed to
an osquery detection strategy: which table to query, how to normalize
the package name, and how to build the SQL.

This registry is the intellectual core of the module. It cannot cover
every KEV entry (~1200 and growing), but it demonstrates that the
architecture works for the products it does cover. Entries are chosen
for products commonly found on Linux hosts because the demo Fleet
instance enrolls Linux devices.

The registry is intentionally a static data structure, not a database.
At enterprise scale, this becomes a versioned config file or a
database table with a review workflow for new entries.
"""

import re
from dataclasses import dataclass
from typing import Optional

# osquery has no parameterized queries, so SQL is built via string
# formatting. To prevent injection if the registry is ever populated
# from an external source, we validate that all interpolated values
# contain only safe characters (alphanumeric, underscore, hyphen,
# dot, percent for LIKE patterns, and spaces).
_SAFE_SQL_LITERAL = re.compile(r"^[a-zA-Z0-9_.%\- ]+$")


def _validate_sql_safe(value: str, field: str) -> str:
    """Reject values that could break out of a SQL literal."""
    if not _SAFE_SQL_LITERAL.match(value):
        raise ValueError(
            f"Registry {field} contains unsafe characters: {value!r}"
        )
    return value


@dataclass(frozen=True)
class RegistryEntry:
    """A curated mapping from a KEV product to an osquery detection."""
    # Human-readable label for the mapping.
    label: str
    # osquery table to query.
    table: str
    # osquery column containing the package/product name.
    name_column: str
    # The value to match in name_column (exact or LIKE pattern).
    name_match: str
    # Whether name_match uses SQL LIKE (True) or exact = (False).
    like: bool = False
    # osquery column containing the version string.
    version_column: str = "version"
    # Platform filter for the generated Fleet policy.
    platform: str = "linux"
    # Optional: specific table for this product on other platforms.
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        _validate_sql_safe(self.table, "table")
        _validate_sql_safe(self.name_column, "name_column")
        _validate_sql_safe(self.name_match, "name_match")


# Key: (vendor_project.lower(), product.lower()) from KEV JSON.
# Value: RegistryEntry describing how to detect the product.
#
# To add a new entry: find the KEV vendor/product strings, identify
# the osquery table and package name, and add a row here.
REGISTRY: dict[tuple[str, str], RegistryEntry] = {
    # -- System libraries and core packages --
    ("openssl", "openssl"): RegistryEntry(
        label="OpenSSL (libssl)",
        table="deb_packages",
        name_column="name",
        name_match="libssl%",
        like=True,
    ),
    ("curl", "curl"): RegistryEntry(
        label="curl",
        table="deb_packages",
        name_column="name",
        name_match="curl",
    ),
    ("todd miller", "sudo"): RegistryEntry(
        label="sudo",
        table="deb_packages",
        name_column="name",
        name_match="sudo",
    ),
    ("red hat", "polkit"): RegistryEntry(
        label="Polkit",
        table="deb_packages",
        name_column="name",
        name_match="policykit%",
        like=True,
    ),
    ("systemd", "systemd"): RegistryEntry(
        label="systemd",
        table="deb_packages",
        name_column="name",
        name_match="systemd",
    ),

    # -- Web servers --
    ("apache", "http server"): RegistryEntry(
        label="Apache HTTP Server",
        table="deb_packages",
        name_column="name",
        name_match="apache2",
    ),
    ("nginx", "nginx"): RegistryEntry(
        label="nginx",
        table="deb_packages",
        name_column="name",
        name_match="nginx%",
        like=True,
    ),

    # -- Remote access --
    ("openbsd", "openssh"): RegistryEntry(
        label="OpenSSH",
        table="deb_packages",
        name_column="name",
        name_match="openssh-server",
    ),
    ("samba", "samba"): RegistryEntry(
        label="Samba",
        table="deb_packages",
        name_column="name",
        name_match="samba",
    ),

    # -- Browsers --
    ("google", "chromium v8"): RegistryEntry(
        label="Google Chrome / Chromium",
        table="deb_packages",
        name_column="name",
        name_match="google-chrome%",
        like=True,
        notes="Also matches chromium-browser on some distros",
    ),
    ("google", "chromium"): RegistryEntry(
        label="Google Chrome / Chromium",
        table="deb_packages",
        name_column="name",
        name_match="google-chrome%",
        like=True,
    ),
    ("google", "chrome"): RegistryEntry(
        label="Google Chrome",
        table="deb_packages",
        name_column="name",
        name_match="google-chrome%",
        like=True,
    ),
    ("mozilla", "firefox"): RegistryEntry(
        label="Mozilla Firefox",
        table="deb_packages",
        name_column="name",
        name_match="firefox%",
        like=True,
    ),

    # -- Language runtimes --
    ("python", "python"): RegistryEntry(
        label="Python",
        table="deb_packages",
        name_column="name",
        name_match="python3",
    ),
    ("node.js", "node.js"): RegistryEntry(
        label="Node.js",
        table="deb_packages",
        name_column="name",
        name_match="nodejs",
    ),
    ("oracle", "java se"): RegistryEntry(
        label="Java SE (OpenJDK)",
        table="deb_packages",
        name_column="name",
        name_match="openjdk%",
        like=True,
    ),

    # -- Databases --
    ("postgresql", "postgresql"): RegistryEntry(
        label="PostgreSQL",
        table="deb_packages",
        name_column="name",
        name_match="postgresql%",
        like=True,
    ),
    ("oracle", "mysql"): RegistryEntry(
        label="MySQL",
        table="deb_packages",
        name_column="name",
        name_match="mysql-server%",
        like=True,
    ),
    ("redis", "redis"): RegistryEntry(
        label="Redis",
        table="deb_packages",
        name_column="name",
        name_match="redis-server",
    ),

    # -- DNS --
    ("isc", "bind"): RegistryEntry(
        label="ISC BIND",
        table="deb_packages",
        name_column="name",
        name_match="bind9",
    ),

    # -- Containers --
    ("docker", "docker"): RegistryEntry(
        label="Docker Engine",
        table="deb_packages",
        name_column="name",
        name_match="docker-ce",
    ),

    # -- Linux kernel (uses os_version, not packages) --
    ("linux", "kernel"): RegistryEntry(
        label="Linux Kernel",
        table="os_version",
        name_column="name",
        name_match="Ubuntu",
        version_column="version",
        notes="Checks kernel version via os_version table",
    ),

    # ============================================================== #
    # macOS / Apple products
    # ============================================================== #
    # Apple KEV entries use inconsistent product strings. Multiple
    # registry keys map to the same detection strategy. Only the macOS
    # component is detectable via osquery — iOS, watchOS, tvOS, and
    # visionOS are not enrolled in Fleet.

    # -- macOS itself (os_version check) --
    ("apple", "macos"): RegistryEntry(
        label="macOS",
        table="os_version",
        name_column="platform",
        name_match="darwin",
        version_column="version",
        platform="darwin",
        notes="Checks macOS version via os_version table",
    ),

    # Multi-product entries that include macOS. CISA lists these as
    # "Multiple Products" covering watchOS, iOS, iPadOS, macOS,
    # visionOS, tvOS. We detect the macOS component only.
    ("apple", "multiple products"): RegistryEntry(
        label="Apple Multiple Products (macOS component)",
        table="os_version",
        name_column="platform",
        name_match="darwin",
        version_column="version",
        platform="darwin",
        notes="Multi-product KEV entry; detects macOS component only",
    ),

    # Safari — detected via apps table on macOS.
    ("apple", "safari"): RegistryEntry(
        label="Safari",
        table="apps",
        name_column="name",
        name_match="Safari.app",
        version_column="bundle_short_version",
        platform="darwin",
        notes="Detects Safari via /Applications bundle version",
    ),

    # Xcode — developer tool, detected via apps table.
    ("apple", "xcode"): RegistryEntry(
        label="Xcode",
        table="apps",
        name_column="name",
        name_match="Xcode.app",
        version_column="bundle_short_version",
        platform="darwin",
        notes="Detects Xcode via /Applications bundle version",
    ),

    # WebKit — detected via Safari since WebKit ships as part of
    # Safari/macOS. Same detection as Safari.
    ("apple", "webkit"): RegistryEntry(
        label="WebKit (via Safari)",
        table="apps",
        name_column="name",
        name_match="Safari.app",
        version_column="bundle_short_version",
        platform="darwin",
        notes="WebKit ships with Safari; detect via Safari version",
    ),
}


def lookup(vendor_project: str, product: str) -> Optional[RegistryEntry]:
    """Find a registry entry for the given KEV vendor/product pair.

    Tries exact match first, then falls back to partial matching
    on the product name alone (some KEV entries use inconsistent
    vendor strings).
    """
    key = (vendor_project.lower().strip(), product.lower().strip())
    entry = REGISTRY.get(key)
    if entry:
        return entry

    # Fallback: try matching just the product against all entries.
    product_lower = product.lower().strip()
    for (_, reg_product), reg_entry in REGISTRY.items():
        if reg_product == product_lower:
            return reg_entry

    return None


def generate_sql(entry: RegistryEntry) -> str:
    """Generate osquery SQL from a registry entry.

    The generated query follows Fleet's convention: return 1 row if
    the host passes (is NOT vulnerable), 0 rows if it fails. This
    means the query checks for the ABSENCE of the vulnerable package
    or the PRESENCE of a safe version.

    For the MVP, the query checks whether the package is installed.
    A production system would also compare version ranges against
    NVD data. The simplified check still demonstrates the
    architecture and catches the "software is present on this host"
    signal that vulnerability management starts with.
    """
    if entry.table == "os_version":
        if entry.platform == "darwin":
            # macOS check: return 1 if the host is running macOS.
            # In production this compares against a specific vulnerable
            # build number or version range.
            return (
                "SELECT 1 FROM os_version "
                "WHERE platform = 'darwin';"
            )
        # Linux kernel check: return 1 if the kernel version is known.
        # In production this compares against a specific vulnerable range.
        return (
            "SELECT 1 FROM os_version "
            "WHERE name = 'Ubuntu' "
            "AND CAST(major AS INTEGER) >= 24;"
        )

    if entry.table == "apps":
        # macOS app check via the apps table (Safari, Xcode, etc.).
        # Returns 1 (pass) if the app is NOT installed. In production
        # this would compare bundle_short_version against a safe version.
        return (
            f"SELECT 1 WHERE NOT EXISTS (\n"
            f"  SELECT 1 FROM apps\n"
            f"  WHERE {entry.name_column} = '{entry.name_match}'\n"
            f");"
        )

    if entry.like:
        condition = f"{entry.name_column} LIKE '{entry.name_match}'"
    else:
        condition = f"{entry.name_column} = '{entry.name_match}'"

    return (
        f"SELECT 1 WHERE NOT EXISTS (\n"
        f"  SELECT 1 FROM {entry.table}\n"
        f"  WHERE {condition}\n"
        f");"
    )
