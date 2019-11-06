# Copyright 2017-present Kensho Technologies, LLC.
import six


def merge_non_overlapping_dicts(merge_target, new_data):
    """Produce the merged result of two dicts that are supposed to not overlap."""
    result = dict(merge_target)

    for key, value in six.iteritems(new_data):
        if key in merge_target:
            raise AssertionError(u'Overlapping key "{}" found in dicts that are supposed '
                                 u'to not overlap. Values: {} {}'
                                 .format(key, merge_target[key], value))

        result[key] = value

    return result


class TriState:
    """A class designed to implement three-value logic."""

    def __init__(self, value):
        """Return a TriState instance.

        Args:
            value: Optional[bool, None]

        Returns:
            A TriState instance.
        """
        if value not in [True, False, None]:
            raise AssertionError('Tristate value must be either True, False, or None.')
        self._value = value

    @property
    def value(self):
        """Return True, False or None depending on whether the value is True, False or Unknown."""
        return self._value

    def __bool__(self):  # python3
        """Called to implement truth value testing."""
        raise ValueError('Cannot implicitly convert Tristate to a boolean.')

    def __nonzero__(self):  # python2
        """Called to implement truth value testing."""
        return self.__bool__()

    def __eq__(self, other):
        """Return True if the TriState is equal to other. Else return False."""
        if not isinstance(other, TriState):
            return False
        else:
            return self.value == other.value

    def __ne__(self, other):
        """Return True if the TriState is not equal to other. Else return False."""
        return not self == other

    def __str__(self):
        """Return a human-readable unicode representation of this TriState."""
        return str(self.value)

    def __repr__(self):
        """Return the "official" representation of the TriState."""
        return 'Tristate({})'.format(self.value)
