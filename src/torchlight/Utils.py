#!/usr/bin/python3
# -*- coding: utf-8 -*-
import math
from typing import Any, Optional


class DataHolder:
    def __init__(self, value: Optional[Any] = None, attr_name: str = 'value'):
        self._attr_name = attr_name
        self.set(value)

    def __call__(self, value: Optional[Any]) -> Optional[Any]:
        return self.set(value)

    def set(self, value: Optional[Any]) -> Optional[Any]:
        setattr(self, self._attr_name, value)
        return value

    def get(self) -> Optional[Any]:
        return getattr(self, self._attr_name)


class Utils:
    @staticmethod
    def GetNum(Text: str) -> str:
        Ret = ''
        for c in Text:
            if c.isdigit():
                Ret += c
            elif Ret:
                break
            elif c == '-':
                Ret += c

        return Ret

    @staticmethod
    def ParseTime(TimeStr: Optional[str]) -> int:
        Negative = False
        Time = 0

        while TimeStr:
            Valraw = Utils.GetNum(TimeStr)
            if not Valraw:
                break

            Val = int(Valraw)
            if not Val:
                break

            if Val < 0:
                TimeStr = TimeStr[1:]
                if Time == 0:
                    Negative = True
            Val = abs(Val)

            ValLen = int(math.log10(Val)) + 1
            if len(TimeStr) > ValLen:
                Mult = TimeStr[ValLen].lower()
                TimeStr = TimeStr[ValLen + 1 :]
                if Mult == 'h':
                    Val *= 3600
                elif Mult == 'm':
                    Val *= 60
            else:
                TimeStr = None

            Time += Val

        if Negative:
            return -Time
        else:
            return Time

    @staticmethod
    def HumanSize(size_bytes: int) -> str:
        """
        format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
        Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
        e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
        """
        if size_bytes == 1:
            # because I really hate unnecessary plurals
            return "1 byte"

        suffixes_table = [
            ('bytes', 0),
            ('KB', 0),
            ('MB', 1),
            ('GB', 2),
            ('TB', 2),
            ('PB', 2),
        ]

        num = float(size_bytes)
        for suffix, precision in suffixes_table:
            if num < 1024.0:
                break
            num /= 1024.0

        if precision == 0:
            formatted_size = str(int(num))
        else:
            formatted_size = str(round(num, ndigits=precision))

        return "{0}{1}".format(formatted_size, suffix)
