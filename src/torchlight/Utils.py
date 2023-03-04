#!/usr/bin/python3
import math


class Utils:
    @staticmethod
    def GetNum(text_num: str) -> str:
        ret = ""
        for c in text_num:
            if c.isdigit():
                ret += c
            elif ret:
                break
            elif c == "-":
                ret += c

        return ret

    @staticmethod
    def ParseTime(time_str: str | None) -> int:
        negative = False
        real_time = 0

        while time_str:
            val_raw = Utils.GetNum(time_str)
            if not val_raw:
                break

            val = int(val_raw)
            if not val:
                break

            if val < 0:
                time_str = time_str[1:]
                if real_time == 0:
                    negative = True
            val = abs(val)

            val_len = int(math.log10(val)) + 1
            if len(time_str) > val_len:
                Mult = time_str[val_len].lower()
                time_str = time_str[val_len + 1 :]
                if Mult == "h":
                    val *= 3600
                elif Mult == "m":
                    val *= 60
            else:
                time_str = None

            real_time += val

        if negative:
            return -real_time
        else:
            return real_time

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
            ("bytes", 0),
            ("KB", 0),
            ("MB", 1),
            ("GB", 2),
            ("TB", 2),
            ("PB", 2),
        ]

        num = float(size_bytes)

        suffix = suffixes_table[0][0]
        precision = 0
        for suffix_table, precision_table in suffixes_table:
            if num < 1024.0:
                suffix = suffix_table
                precision = precision_table
                break
            num /= 1024.0

        if precision == 0:
            formatted_size = str(int(num))
        else:
            formatted_size = str(round(num, ndigits=precision))

        return f"{formatted_size}{suffix}"
