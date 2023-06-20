import typing
from enum import Enum

from .utils import OVEException


class ValidationStatus(Enum):
    VALIDATED = 0
    EMPTY = 1
    ERROR = 2


class DisplayType(Enum):
    FLEX = 0
    PIXEL = 1
    GRID = 2
    AUTOMATIC = 3


class LayoutValidator:

    @staticmethod
    def validate_pixels(args: dict) -> ValidationStatus:
        if args.width is not None and args.height is not None and args.x is not None and args.y is not None:
            return ValidationStatus.VALIDATED
        elif args.width is None and args.height is None and args.x is None and args.y is None:
            return ValidationStatus.EMPTY
        else:
            return ValidationStatus.ERROR

    @staticmethod
    def validate_grid(args: dict) -> ValidationStatus:
        if args.row is not None and args.col is not None:
            return ValidationStatus.VALIDATED
        elif args.row is None and args.col is None:
            return ValidationStatus.EMPTY
        else:
            return ValidationStatus.ERROR

    @staticmethod
    def validate_flex(args: dict) -> ValidationStatus:
        def helper(x: typing.Any) -> bool:
            return x is not None and hasattr(x, "__len__") and len(x) == 2

        if helper(args.from_) and helper(args.to_) and args.to_[0] > args.from_[0] and args.to_[1] > args.from_[1]:
            return ValidationStatus.VALIDATED
        elif args.from_ is None and args.to_ is None:
            return ValidationStatus.EMPTY
        else:
            return ValidationStatus.ERROR

    def validate(self, args: dict) -> DisplayType:
        if args.cell_no is None:
            raise OVEException("No id provided")

        validation = self.validate_flex(args), self.validate_pixels(args), self.validate_grid(args)

        if validation.count(ValidationStatus.VALIDATED) != 1 and validation.count(ValidationStatus.EMPTY) != len(
                validation):
            raise OVEException("Invalid cell config")

        if validation.count(ValidationStatus.EMPTY) == len(validation):
            return DisplayType.AUTOMATIC
        return DisplayType(validation.index(ValidationStatus.VALIDATED))
