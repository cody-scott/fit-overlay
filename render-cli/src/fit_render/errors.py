"""Exception hierarchy. Every error a user can cause derives from FitRenderError,
so the CLI can print a clean message instead of a traceback."""


class FitRenderError(Exception):
    """Base class for all expected, user-facing errors."""


class ActivityParseError(FitRenderError):
    """The activity file could not be read or contains no usable records."""


class UnsupportedFileError(FitRenderError):
    """No parser is registered for the given file type."""


class SpecError(FitRenderError):
    """The overlay spec / template is invalid."""


class SliceError(FitRenderError):
    """The requested start/end slice is invalid for this activity."""


class EncoderError(FitRenderError):
    """ffmpeg is missing or failed while encoding."""
