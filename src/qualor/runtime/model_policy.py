"""Separate bounded planning and focused extraction output allowances."""

STRANDS_MAX_OUTPUT_TOKENS = 512
# Two measured distinct owned claims serialize to 801 UTF-8 bytes. A one-token-per-byte
# upper estimate plus 223 tokens of headroom fits 1024; this is not a promise
# that arbitrary values or every valid domain batch fit. Truncation fails closed.
EXTRACTION_MAX_OUTPUT_TOKENS = 1024
