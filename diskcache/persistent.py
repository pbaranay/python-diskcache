"""Persistent Data Types

"""

import operator as op
import sys

from collections import MutableMapping, OrderedDict, Sequence
from itertools import islice
from shutil import rmtree
from tempfile import mkdtemp

from .core import BytesType, Cache, ENOVAL, TextType, Timeout

if sys.hexversion < 0x03000000:
    from itertools import izip as zip  # pylint: disable=redefined-builtin,ungrouped-imports,wrong-import-order
    range = xrange  # pylint: disable=redefined-builtin,invalid-name


def _make_compare(seq_op, doc):
    "Make compare method with Sequence semantics."
    def compare(self, that):
        "Compare method for deque and sequence."
        if not isinstance(that, Sequence):
            return NotImplemented

        len_self = len(self)
        len_that = len(that)

        if len_self != len_that:
            if seq_op is op.eq:
                return False
            if seq_op is op.ne:
                return True

        for alpha, beta in zip(self, that):
            if alpha != beta:
                return seq_op(alpha, beta)

        return seq_op(len_self, len_that)

    compare.__name__ = '__{0}__'.format(seq_op.__name__)
    doc_str = 'Return True if and only if deque is {0} `that`.'
    compare.__doc__ = doc_str.format(doc)

    return compare


class Deque(Sequence):
    """Persistent sequence with double-ended queue semantics.

    Double-ended queue is an ordered collection with optimized access at its
    endpoints.

    Items are serialized to disk. Deque may be initialized from directory path
    where items are stored.

    >>> deque = Deque()
    >>> for value in range(5):
    ...     deque.append(value)
    >>> list(deque)
    [0, 1, 2, 3, 4]
    >>> for value in range(5):
    ...     deque.appendleft(-value)
    >>> list(deque)
    [-4, -3, -2, -1, 0, 0, 1, 2, 3, 4]
    >>> deque.pop()
    4
    >>> deque.popleft()
    -4

    """
    def __init__(self, iterable=(), directory=None):
        """Initialize deque instance.

        If directory is None then temporary directory created. The directory
        will *not* be automatically removed.

        :param iterable: iterable of items to append to deque
        :param directory: deque directory (default None)

        """
        if directory is None:
            directory = mkdtemp()
        self._cache = Cache(directory, eviction_policy='none')
        self.extend(iterable)


    @property
    def directory(self):
        "Directory path where deque is stored."
        return self._cache.directory


    def _key(self, index):
        len_self = len(self)

        if index < 0:
            index += len_self
            if index < 0:
                raise IndexError('deque index out of range')
        elif index >= len_self:
            raise IndexError('deque index out of range')

        diff = len_self - index - 1
        _cache_iterkeys = self._cache.iterkeys

        try:
            if index <= diff:
                iter_keys = _cache_iterkeys()
                key = next(islice(iter_keys, index, index + 1))
            else:
                iter_keys = _cache_iterkeys(reverse=True)
                key = next(islice(iter_keys, diff, diff + 1))
        except StopIteration:
            raise IndexError('deque index out of range')

        return key


    def __getitem__(self, index):
        """deque.__getitem__(index) <==> deque[index]

        Return corresponding item for `index` in deque.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque.extend('abcde')
        >>> deque[0]
        'a'
        >>> deque[-1]
        'e'
        >>> deque[2]
        'c'

        :param int index: index of item
        :return: corresponding item
        :raises IndexError: if index out of range

        """
        _key = self._key
        _cache = self._cache

        while True:
            try:
                key = _key(index)
                return _cache[key]
            except (KeyError, Timeout):
                continue


    def __setitem__(self, index, value):
        """deque.__setitem__(index, value) <==> deque[index] = value

        Store `value` in deque at `index`.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque.extend([None] * 3)
        >>> deque[0] = 'a'
        >>> deque[1] = 'b'
        >>> deque[-1] = 'c'
        >>> ''.join(deque)
        'abc'

        :param int index: index of value
        :param value: value to store
        :raises IndexError: if index out of range

        """
        _key = self._key
        _cache = self._cache

        while True:
            try:
                key = _key(index)
                _cache[key] = value
                return
            except Timeout:
                continue


    def __delitem__(self, index):
        """deque.__delitem__(index) <==> del deque[index]

        Delete item in deque at `index`.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque.extend([None] * 3)
        >>> del deque[0]
        >>> del deque[1]
        >>> del deque[-1]
        >>> len(deque)
        0

        :param int index: index of item
        :raises IndexError: if index out of range

        """
        _key = self._key
        _cache = self._cache

        while True:
            try:
                key = _key(index)
                del _cache[key]
                return
            except (KeyError, Timeout):
                continue


    def __repr__(self):
        """deque.__repr__() <==> repr(deque)

        Return string with printable representation of deque.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque
        Deque(directory='/tmp/diskcache/deque')

        """
        name = type(self).__name__
        return '{0}(directory={1!r})'.format(name, self.directory)


    __eq__ = _make_compare(op.eq, 'equal to')
    __ne__ = _make_compare(op.ne, 'not equal to')
    __lt__ = _make_compare(op.lt, 'less than')
    __gt__ = _make_compare(op.gt, 'greater than')
    __le__ = _make_compare(op.le, 'less than or equal to')
    __ge__ = _make_compare(op.ge, 'greater than or equal to')


    def __iadd__(self, iterable):
        """deque.__iadd__(iterable) <==> deque += iterable

        Extend back side of deque with items from iterable.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque += 'abc'
        >>> list(deque)
        ['a', 'b', 'c']

        """
        self.extend(iterable)
        return self


    def __iter__(self):
        """deque.__iter__() <==> iter(deque)

        Return iterator of deque from front to back.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque += 'abc'
        >>> iterator = iter(deque)
        >>> next(iterator)
        'a'
        >>> list(iterator)
        ['b', 'c']

        """
        _cache = self._cache

        for key in _cache.iterkeys():
            try:
                yield _cache[key]
            except (KeyError, Timeout):
                pass


    def __len__(self):
        """deque.__len__() <==> len(deque)

        Return length of deque.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> len(deque)
        0
        >>> deque.extend('abc')
        >>> len(deque)
        3

        """
        return len(self._cache)


    def __reversed__(self):
        """deque.__reversed__() <==> reversed(deque)

        Return iterator of deque from back to front.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque.extend('abc')
        >>> iterator = reversed(deque)
        >>> next(iterator)
        'c'
        >>> list(iterator)
        ['b', 'a']

        """
        _cache = self._cache

        for key in _cache.iterkeys(reverse=True):
            try:
                yield _cache[key]
            except (KeyError, Timeout):
                pass


    def __getstate__(self):
        return self.directory


    def __setstate__(self, state):
        self.__init__(directory=state)


    def append(self, value):
        """Add `value` to back of deque.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque.append('a')
        >>> deque.append('b')
        >>> deque.append('c')
        >>> list(deque)
        ['a', 'b', 'c']

        :param value: value to add to back of deque

        """
        _cache_push = self._cache.push

        while True:
            try:
                _cache_push(value)
                return
            except Timeout:
                continue


    def appendleft(self, value):
        """Add `value` to front of deque.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque.appendleft('a')
        >>> deque.appendleft('b')
        >>> deque.appendleft('c')
        >>> list(deque)
        ['c', 'b', 'a']

        :param value: value to add to front of deque

        """
        _cache_push = self._cache.push

        while True:
            try:
                _cache_push(value, side='front')
                return
            except Timeout:
                continue


    def clear(self):
        """Remove all elements from deque.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque += range(10)
        >>> len(deque)
        10
        >>> deque.clear()
        >>> len(deque)
        0

        """
        _cache_clear = self._cache.clear

        while True:
            try:
                _cache_clear()
                return
            except Timeout:
                continue


    def count(self, value):
        """Return number of occurrences of `value` in deque.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque += [num for num in range(1, 5) for _ in range(num)]
        >>> deque.count(0)
        0
        >>> deque.count(1)
        1
        >>> deque.count(4)
        4

        :param value: value to count in deque

        """
        return sum(1 for item in self if item == value)


    def extend(self, iterable):
        """Extend back side of deque with values from `iterable`.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque.extend('abc')
        >>> list(deque)
        ['a', 'b', 'c']

        :param iterable: iterable of values

        """
        for value in iterable:
            self.append(value)


    def extendleft(self, iterable):
        """Extend front side of deque with value from `iterable`.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque.extendleft('abc')
        >>> list(deque)
        ['c', 'b', 'a']

        :param iterable: iterable of values

        """
        for value in iterable:
            self.appendleft(value)


    def pop(self):
        """Remove and return value at back of deque.

        If deque is empty then raise IndexError.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque += 'ab'
        >>> deque.pop()
        'b'
        >>> deque.pop()
        'a'
        >>> deque.pop()
        Traceback (most recent call last):
            ...
        IndexError: pop from an empty deque

        :raises IndexError: if deque is empty

        """
        _cache_pull = self._cache.pull

        while True:
            try:
                default = None, ENOVAL
                _, value = _cache_pull(default=default, side='back')
            except Timeout:
                continue
            else:
                if value is ENOVAL:
                    raise IndexError('pop from an empty deque')
                return value


    def popleft(self):
        """Remove and return value at front of deque.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque += 'ab'
        >>> deque.popleft()
        'a'
        >>> deque.popleft()
        'b'
        >>> deque.popleft()
        Traceback (most recent call last):
            ...
        IndexError: pop from an empty deque

        """
        _cache_pull = self._cache.pull

        while True:
            try:
                default = None, ENOVAL
                _, value = _cache_pull(default=default)
            except Timeout:
                continue
            else:
                if value is ENOVAL:
                    raise IndexError('pop from an empty deque')
                return value


    def remove(self, value):
        """Remove first occurrence of `value` in deque.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque += 'aab'
        >>> deque.remove('a')
        >>> list(deque)
        ['a', 'b']
        >>> deque.remove('b')
        >>> list(deque)
        ['a']
        >>> deque.remove('c')
        Traceback (most recent call last):
            ...
        ValueError: deque.remove(value): value not in deque

        :param value: value to remove
        :raises ValueError: if value not in deque

        """
        _cache = self._cache

        for key in _cache.iterkeys():
            try:
                item = _cache[key]
            except KeyError:
                continue
            else:
                if value == item:
                    try:
                        while True:
                            try:
                                del _cache[key]
                            except Timeout:
                                continue
                            else:
                                return
                    except KeyError:
                        continue

        raise ValueError('deque.remove(value): value not in deque')


    def reverse(self):
        """Reverse deque in place.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque.extend('abc')
        >>> deque.reverse()
        >>> list(deque)
        ['c', 'b', 'a']

        """
        directory = mkdtemp()
        temp = None

        try:
            temp = Deque(iterable=reversed(self), directory=directory)
            self.clear()
            self.extend(temp)
        finally:
            del temp
            rmtree(directory)


    def rotate(self, steps=1):
        """Rotate deque right by `steps`.

        If steps is negative then rotate left.

        >>> deque = Deque(directory='/tmp/diskcache/deque')
        >>> deque.clear()
        >>> deque += range(5)
        >>> deque.rotate(2)
        >>> list(deque)
        [3, 4, 0, 1, 2]
        >>> deque.rotate(-1)
        >>> list(deque)
        [4, 0, 1, 2, 3]

        :param int steps: number of steps to rotate (default 1)

        """
        if not isinstance(steps, int):
            type_name = type(steps).__name__
            raise TypeError('integer argument expected, got %s' % type_name)

        if steps >= 0:
            for _ in range(steps):
                try:
                    value = self.pop()
                except IndexError:
                    return
                else:
                    self.appendleft(value)
        else:
            for _ in range(-steps):
                try:
                    value = self.popleft()
                except IndexError:
                    return
                else:
                    self.append(value)


    __hash__ = None


class Index(MutableMapping):
    """Persistent mutable mapping with insertion order iteration.

    Items are serialized to disk. Index may be initialized from directory path
    where items are stored.

    Hashing protocol is not used. Keys are looked up by their serialized
    format. See ``diskcache.Disk`` for details.

    >>> index = Index([('apple', 1), ('beans', 2), ('cherries', 3)])
    >>> index['apple']
    1
    >>> list(index)
    ['apple', 'beans', 'cherries']
    >>> len(index)
    3
    >>> del index['beans']
    >>> index.popitem()
    ('cherries', 3)

    """
    def __init__(self, *args, **kwargs):
        """Initialize index in directory and update items.

        Optional first argument may be string specifying directory where items
        are stored. When None or not given, temporary directory is created.

        >>> index = Index({'apples': 1, 'beans': 2, 'cherries': 3})
        >>> len(index)
        3
        >>> directory = index.directory
        >>> inventory = Index(directory, dates=4)
        >>> inventory['beans']
        2
        >>> len(inventory)
        4

        """
        if args and isinstance(args[0], (BytesType, TextType)):
            directory = args[0]
            args = args[1:]
        else:
            if args and args[0] is None:
                args = args[1:]
            directory = mkdtemp(prefix='diskcache-')
        self._cache = Cache(directory, eviction_policy='none', timeout=0.001)
        self.update(*args, **kwargs)


    @property
    def directory(self):
        "Directory path where items are stored."
        return self._cache.directory


    def __getitem__(self, key):
        """index.__getitem__(key) <==> index[key]

        Return corresponding value for `key` in index.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> index.update({'a': 0, 'b': 1})
        >>> index['a']
        0
        >>> index['b']
        1
        >>> index['c']
        Traceback (most recent call last):
            ...
        KeyError: 'c'

        :param key: key for item
        :raises KeyError: if key is not found

        """
        _cache = self._cache

        while True:
            try:
                return _cache[key]
            except Timeout:
                continue


    def __setitem__(self, key, value):
        """index.__setitem__(key, value) <==> index[key] = value

        Set `key` and `value` item in index.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> index['a'] = 0
        >>> index[0] = None
        >>> len(index)
        2

        :param key: key for item
        :param value: value for item

        """
        _cache = self._cache

        while True:
            try:
                _cache[key] = value
            except Timeout:
                continue
            else:
                return


    def __delitem__(self, key):
        """index.__delitem__(key) <==> del index[key]

        Delete corresponding item for `key` from index.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> index.update({'a': 0, 'b': 1})
        >>> del index['a']
        >>> del index['b']
        >>> len(index)
        0
        >>> del index['c']
        Traceback (most recent call last):
            ...
        KeyError: 'c'

        :param key: key for item
        :raises KeyError: if key is not found

        """
        _cache = self._cache

        while True:
            try:
                del _cache[key]
            except Timeout:
                continue
            else:
                return


    def pop(self, key, default=ENOVAL):
        """Remove corresponding item for `key` from index and return value.

        If `key` is missing then return `default`. If `default` is `ENOVAL`
        then raise KeyError.

        >>> index = Index('/tmp/diskcache/index', {'a': 0, 'b': 1})
        >>> index.pop('a')
        0
        >>> index.pop('b')
        1
        >>> index.pop('c', default=2)
        2
        >>> index.pop('d')
        Traceback (most recent call last):
            ...
        KeyError: 'd'

        :param key: key for item
        :param default: return value if key is missing (default ENOVAL)
        :return: value for item if key is found else default
        :raises KeyError: if key is not found and default is ENOVAL

        """

        _cache = self._cache

        while True:
            try:
                value = _cache.pop(key, default=default)
            except Timeout:
                continue
            else:
                if value is ENOVAL:
                    raise KeyError(key)
                return value


    def popitem(self, last=True):
        """Remove and return item pair.

        Item pairs are returned in last-in-first-out (LIFO) order if last is
        True else first-in-first-out (FIFO) order. LIFO order imitates a stack
        and FIFO order imitates a queue.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> index.update([('apples', 1), ('beans', 2), ('cherries', 3)])
        >>> index.popitem()
        ('cherries', 3)
        >>> index.popitem()
        ('beans', 2)
        >>> index.popitem()
        ('apples', 1)
        >>> index.popitem()
        Traceback (most recent call last):
          ...
        KeyError

        :param bool last: pop last item pair (default True)
        :return: key and value item pair
        :raises KeyError: if index is empty

        """
        # pylint: disable=arguments-differ
        _cache = self._cache

        while True:
            try:
                if last:
                    key = next(reversed(_cache))
                else:
                    key = next(iter(_cache))
            except StopIteration:
                raise KeyError

            try:
                value = _cache.pop(key)
            except (KeyError, Timeout):
                continue
            else:
                return key, value


    def push(self, value, prefix=None, side='back'):
        """Push `value` onto `side` of queue in index identified by `prefix`.

        When prefix is None, integer keys are used. Otherwise, string keys are
        used in the format "prefix-integer". Integer starts at 500 trillion.

        Defaults to pushing value on back of queue. Set side to 'front' to push
        value on front of queue. Side must be one of 'back' or 'front'.

        See also `Index.pull`.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> index.push('apples')
        500000000000000
        >>> index.push('beans')
        500000000000001
        >>> index.push('cherries', side='front')
        499999999999999
        >>> index[500000000000001]
        'beans'
        >>> index.push('dates', prefix='fruit')
        'fruit-500000000000000'

        :param value: value for item
        :param str prefix: key prefix (default None, key is integer)
        :param str side: either 'back' or 'front' (default 'back')
        :return: key for item in cache

        """
        _cache_push = self._cache.push

        while True:
            try:
                return _cache_push(value, prefix, side)
            except Timeout:
                continue


    def pull(self, prefix=None, default=(None, None), side='front'):
        """Pull key and value item pair from `side` of queue in index.

        When prefix is None, integer keys are used. Otherwise, string keys are
        used in the format "prefix-integer". Integer starts at 500 trillion.

        If queue is empty, return default.

        Defaults to pulling key and value item pairs from front of queue. Set
        side to 'back' to pull from back of queue. Side must be one of 'front'
        or 'back'.

        See also `Index.push`.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> for letter in 'abc':
        ...     index.push(letter)
        500000000000000
        500000000000001
        500000000000002
        >>> index.pull()
        (500000000000000, 'a')
        >>> index.pull(side='back')
        (500000000000002, 'c')
        >>> index.pull(prefix='fruit')
        (None, None)

        :param str prefix: key prefix (default None, key is integer)
        :param default: value to return if key is missing
            (default (None, None))
        :param str side: either 'front' or 'back' (default 'front')
        :return: key and value item pair or default if queue is empty

        """
        _cache_pull = self._cache.pull

        while True:
            try:
                return _cache_pull(prefix, default, side)
            except Timeout:
                continue


    def clear(self):
        """Remove all items from index.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> index.update({'a': 0, 'b': 1, 'c': 2})
        >>> len(index)
        3
        >>> index.clear()
        >>> len(index)
        0

        """
        _cache_clear = self._cache.clear

        while True:
            try:
                _cache_clear()
                return
            except Timeout:
                continue


    def __iter__(self):
        """index.__iter__() <==> iter(index)

        Return iterator of index keys in insertion order.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> index.update([('a', 0), ('b', 1), ('c', 2)])
        >>> iterator = iter(index)
        >>> next(iterator)
        'a'
        >>> list(iterator)
        ['b', 'c']

        """
        return iter(self._cache)


    def __reversed__(self):
        """index.__reversed__() <==> reversed(index)

        Return iterator of index keys in reversed insertion order.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> index.update([('a', 0), ('b', 1), ('c', 2)])
        >>> iterator = reversed(index)
        >>> next(iterator)
        'c'
        >>> list(iterator)
        ['b', 'a']

        """
        return reversed(self._cache)


    def __len__(self):
        """index.__len__() <==> len(index)

        Return length of index.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> len(index)
        0
        >>> index.update({'a': 0, 'b': 1, 'c': 2})
        >>> len(index)
        3

        """
        return len(self._cache)


    __hash__ = None


    def __getstate__(self):
        return self.directory


    def __setstate__(self, state):
        self.__init__(state)


    def __eq__(self, other):
        """index.__eq__(other) <==> index == other

        Compare equality for index and `other`.

        Comparison to another index or ordered dictionary is
        order-sensitive. Comparison to all other mappings is order-insensitive.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> pairs = [('a', 0), ('b', 1), ('c', 2)]
        >>> index.update(pairs)
        >>> from collections import OrderedDict
        >>> od = OrderedDict(pairs)
        >>> index == od
        True
        >>> index == {'c': 2, 'b': 1, 'a': 0}
        True

        :param other: other mapping in equality comparison

        """
        if len(self) != len(other):
            return False

        if isinstance(other, (Index, OrderedDict)):
            alpha = ((key, self[key]) for key in self)
            beta = ((key, other[key]) for key in other)
            pairs = zip(alpha, beta)
            return not any(a != x or b != y for (a, b), (x, y) in pairs)
        else:
            return all(self[key] == other.get(key, ENOVAL) for key in self)


    def __ne__(self, other):
        """index.__ne__(other) <==> index != other

        Compare inequality for index and `other`.

        Comparison to another index or ordered dictionary is
        order-sensitive. Comparison to all other mappings is order-insensitive.

        >>> index = Index('/tmp/diskcache/index')
        >>> index.clear()
        >>> index.update([('a', 0), ('b', 1), ('c', 2)])
        >>> from collections import OrderedDict
        >>> od = OrderedDict([('c', 2), ('b', 1), ('a', 0)])
        >>> index != od
        True
        >>> index != {'a': 0, 'b': 1}
        True

        :param other: other mapping in inequality comparison

        """
        return not self == other


    def __repr__(self):
        """index.__repr__() <==> repr(index)

        Return string with printable representation of index.

        >>> index = Index('/tmp/diskcache/index')
        >>> index
        Index('/tmp/diskcache/index')

        """
        name = type(self).__name__
        return '{0}({1!r})'.format(name, self.directory)