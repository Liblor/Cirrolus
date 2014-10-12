#
# Author: Loris Reiff
# Maturaarbeit
#
import sys


if sys.version > '3':
    integer_types = (int, )
else:
    integer_types = (int, long)


class SimplePolynomial(object):
    """
    A simple one dimensional integer only polynomial class with few methodes
    """
    def __init__(self, coefficients):
        if isinstance(coefficients, (integer_types)):
            self.coefficients = [coefficients]
        elif all(isinstance(i, (integer_types)) for i in coefficients):
            self.coefficients = list(coefficients)
            self._trim_zeros()
        else:
            raise TypeError("unsupported type")

    def _trim_zeros(self):
        """
        Removes leading zeros

        example:
        --------

        [1, 0, 2, 0, 0] --> [1, 0, 2]
        [0] --> []

        """
        try:
            while not self.coefficients[-1]:
                del self.coefficients[-1]
        except IndexError:
            pass

    def __add__(self, other):
        result = self.coefficients[:]
        if isinstance(other, (list, tuple)):
            other = self.__class__(other)
        if isinstance(other, (integer_types)):
            try:
                result[0] += other
            except IndexError:
                result.append(other)
        elif isinstance(other, self.__class__):
            if len(self) > len(other):
                longlist, shortlist = self.coefficients, other.coefficients
            else:
                longlist, shortlist = other.coefficients, self.coefficients
            result = longlist[:]
            for i in range(len(shortlist)):
                result[i] += shortlist[i]
        else:
            return NotImplemented
        return self.__class__(result)

    __radd__ = __add__

    def __mul__(self, other):
        if isinstance(other, (list, tuple)):
            other = self.__class__(other)
        if isinstance(other, (integer_types)):
            result = [other * i for i in self.coefficients]
        elif isinstance(other, self.__class__):
            result = [0] * (len(self) + len(other) - 1)
            for i in range(len(self)):
                for j in range(len(other)):
                    result[i + j] += self[i] * other[j]
        else:
            return NotImplemented
        return self.__class__(result)
    __rmul__ = __mul__

    def __mod__(self, other):
        if isinstance(other, integer_types):
            return self.__class__([x % other for x in self.coefficients])
        else:
            return NotImplemented

    def __repr__(self):
        return "{0}({1})".format(type(self).__name__, str(self.coefficients))

    def __str__(self):
        s = ''
        c_r = self.coefficients[::-1]
        for i in range(len(c_r) - 1):
            if c_r[i]:
                s += "{0} x^{1} + ".format(c_r[i], len(c_r) - i - 1)
        try:
            s += str(c_r[-1])
        except IndexError:
            s = "0"
        return s

    def __call__(self, x, modulo=None):
        sum_ = sum([self[i] * pow(x, i, modulo) for i in range(len(self))])
        if modulo is not None:
            sum_ %= modulo
        return sum_

    def __len__(self):
        return len(self.coefficients)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.coefficients == other.coefficients
        else:
            return NotImplemented

    def __getitem__(self, key):
        return self.coefficients[key]

    def __setitem__(self, key, val):
        if isinstance(val, (integer_types)):
            self.coefficients[key] = val
            self._trim_zeros()
        else:
            raise TypeError("unsupported type")


if __name__ == "__main__":
    o = SimplePolynomial([15545, 245, 35458])
    t = SimplePolynomial([2, 1])
    print(o % 13)
    print(1 + o)
    print(t*o)
