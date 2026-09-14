import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Tuple, Union

    VERSION_TUPLE = Tuple[Union[int, str], ...]
else:
    VERSION_TUPLE = object

version: str
__version__: str
__version_tuple__: VERSION_TUPLE
version_tuple: VERSION_TUPLE

__version__ = version = '0.0.1'
__version_tuple__ = version_tuple = tuple(
    int(part) if part.isdigit() else part for part in re.split(r'\.|(?<=[0-9])(?=[a-zA-Z])', version)
)
