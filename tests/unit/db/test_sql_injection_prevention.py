"""Unit tests for SQL injection prevention via ILIKE escaping.

Tests ensure the _escape_ilike function properly escapes special SQL wildcards
and that the search functionality is not vulnerable to SQL injection.
"""

from __future__ import annotations

from svc_infra.db.sql.repository import _escape_ilike


class TestEscapeIlike:
    """Tests for the _escape_ilike function."""

    def test_escape_percent_wildcard(self):
        """Test that % is escaped to prevent matching any string."""
        result = _escape_ilike("100%")
        assert result == "100\\%"

    def test_escape_underscore_wildcard(self):
        """Test that _ is escaped to prevent matching any single character."""
        result = _escape_ilike("user_name")
        assert result == "user\\_name"

    def test_escape_backslash(self):
        """Test that backslash is escaped first (before other escapes)."""
        result = _escape_ilike("C:\\Users")
        assert result == "C:\\\\Users"

    def test_escape_all_wildcards_combined(self):
        """Test escaping when all special characters are present."""
        result = _escape_ilike("100% off_sale\\end")
        assert result == "100\\% off\\_sale\\\\end"

    def test_empty_string(self):
        """Test escaping empty string."""
        result = _escape_ilike("")
        assert result == ""

    def test_no_special_chars(self):
        """Test string with no special characters passes through unchanged."""
        result = _escape_ilike("hello world")
        assert result == "hello world"


class TestSqlInjectionPatterns:
    """Tests for common SQL injection patterns that should be escaped."""

    def test_escape_percent_injection_match_all(self):
        """Test injection attempt to match all records with %."""
        # Attacker tries: "%" to match everything
        result = _escape_ilike("%")
        assert result == "\\%"  # Now matches literal %

    def test_escape_underscore_injection_single_char(self):
        """Test injection attempt using _ to match single characters."""
        # Attacker tries: "____" to match any 4-char string
        result = _escape_ilike("____")
        assert result == "\\_\\_\\_\\_"

    def test_escape_like_bypass_attempt(self):
        """Test injection attempt to bypass LIKE pattern."""
        # Attacker tries: "%admin%" to match any admin-like record
        result = _escape_ilike("%admin%")
        assert result == "\\%admin\\%"

    def test_escape_sql_comment_in_search(self):
        """Test that SQL comments are treated as literal text."""
        # Attacker tries: "'; DROP TABLE users; --"
        # This should be passed to ILIKE as literal text
        result = _escape_ilike("'; DROP TABLE users; --")
        # No escaping needed - these are not ILIKE wildcards
        # The parameterized query handles SQL injection prevention
        assert result == "'; DROP TABLE users; --"

    def test_escape_unicode_wildcards(self):
        """Test that only ASCII wildcards are escaped."""
        # Unicode characters that look like % or _ should not be escaped
        result = _escape_ilike("café 100％")  # Full-width %
        assert "％" in result  # Full-width % preserved
        assert "\\%" not in result

    def test_escape_multiple_consecutive_wildcards(self):
        """Test multiple consecutive wildcards are all escaped."""
        result = _escape_ilike("%%__%%")
        assert result == "\\%\\%\\_\\_\\%\\%"

    def test_escape_mixed_content(self):
        """Test realistic search terms with accidental wildcards."""
        # User searching for "50% discount on product_123"
        result = _escape_ilike("50% discount on product_123")
        assert result == "50\\% discount on product\\_123"


class TestEdgeCasesEscape:
    """Edge case tests for ILIKE escaping."""

    def test_very_long_string(self):
        """Test escaping very long strings."""
        long_input = "%" * 10000
        result = _escape_ilike(long_input)
        assert result == "\\%" * 10000
        assert len(result) == 20000

    def test_backslash_before_percent(self):
        """Test backslash immediately before percent is handled correctly."""
        # Input: \% (user wants to search for literal \%)
        # Should become: \\%\ (escaped backslash + escaped percent)
        result = _escape_ilike("\\%")
        assert result == "\\\\\\%"

    def test_backslash_before_underscore(self):
        """Test backslash immediately before underscore is handled correctly."""
        result = _escape_ilike("\\_")
        assert result == "\\\\\\_"

    def test_alternating_special_chars(self):
        """Test alternating special characters."""
        result = _escape_ilike("%_%_%")
        assert result == "\\%\\_\\%\\_\\%"

    def test_only_backslashes(self):
        """Test string of only backslashes."""
        result = _escape_ilike("\\\\\\")
        assert result == "\\\\\\\\\\\\"

    def test_whitespace_preserved(self):
        """Test that whitespace is preserved."""
        result = _escape_ilike("  %  _  \\  ")
        assert result == "  \\%  \\_  \\\\  "

    def test_newlines_preserved(self):
        """Test that newlines are preserved."""
        result = _escape_ilike("line1\nline2%")
        assert result == "line1\nline2\\%"

    def test_tabs_preserved(self):
        """Test that tabs are preserved."""
        result = _escape_ilike("col1\tcol2%")
        assert result == "col1\tcol2\\%"

    def test_null_bytes_in_string(self):
        """Test handling of null bytes (edge case)."""
        # This might come from malformed input
        result = _escape_ilike("before\x00after%")
        assert result == "before\x00after\\%"


class TestRealWorldSearchPatterns:
    """Tests simulating real-world search patterns."""

    def test_email_search(self):
        """Test searching for email patterns."""
        # User searches for "john_doe@example.com"
        result = _escape_ilike("john_doe@example.com")
        assert result == "john\\_doe@example.com"

    def test_file_path_search(self):
        """Test searching for file paths."""
        # User searches for "C:\\Users\\Documents"
        result = _escape_ilike("C:\\Users\\Documents")
        assert result == "C:\\\\Users\\\\Documents"

    def test_url_search(self):
        """Test searching for URLs with query params."""
        # URL with % encoded characters: "https://example.com/search?q=50%25off"
        result = _escape_ilike("https://example.com/search?q=50%25off")
        assert result == "https://example.com/search?q=50\\%25off"

    def test_product_sku_search(self):
        """Test searching for product SKUs with underscores."""
        result = _escape_ilike("PROD_ABC_123")
        assert result == "PROD\\_ABC\\_123"

    def test_phone_number_search(self):
        """Test searching for phone numbers (no special chars)."""
        result = _escape_ilike("+1-555-123-4567")
        assert result == "+1-555-123-4567"  # No escaping needed

    def test_currency_with_percent(self):
        """Test searching for discount percentages."""
        result = _escape_ilike("50% off")
        assert result == "50\\% off"

    def test_username_with_underscore(self):
        """Test searching for usernames with underscores."""
        result = _escape_ilike("john_smith_2024")
        assert result == "john\\_smith\\_2024"

    def test_log_message_search(self):
        """Test searching for log messages with special chars."""
        result = _escape_ilike("Error: 100% CPU usage on server_01 at C:\\logs")
        assert result == "Error: 100\\% CPU usage on server\\_01 at C:\\\\logs"


class TestSecurityVectors:
    """Security-focused tests for injection attempts."""

    def test_blind_sql_injection_timing(self):
        """Test that timing-based SQL injection is neutralized."""
        # Attacker tries: "' OR SLEEP(10)--"
        result = _escape_ilike("' OR SLEEP(10)--")
        # These are not ILIKE wildcards, so pass through
        # But they're safely used in parameterized query
        assert result == "' OR SLEEP(10)--"

    def test_union_based_injection(self):
        """Test UNION-based SQL injection is neutralized."""
        result = _escape_ilike("' UNION SELECT * FROM users--")
        assert result == "' UNION SELECT * FROM users--"

    def test_stacked_queries_injection(self):
        """Test stacked queries injection is neutralized."""
        result = _escape_ilike("'; INSERT INTO users VALUES('hacker')--")
        assert result == "'; INSERT INTO users VALUES('hacker')--"

    def test_escape_sequence_bypass(self):
        """Test that escape sequence bypass attempts fail."""
        # Attacker tries: "\\%" hoping \\ becomes \ and % stays wild
        # Our function escapes \\ to \\\\ and % to \%
        result = _escape_ilike("\\%")
        assert result == "\\\\\\%"
        # Now the database sees: \\% which is literal backslash + literal %

    def test_double_encoding_bypass(self):
        """Test double-encoding bypass attempts."""
        # Attacker tries URL-encoded wildcards
        result = _escape_ilike("%25")  # %25 is URL-encoded %
        assert result == "\\%25"  # We escape the % in %25
