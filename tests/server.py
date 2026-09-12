#!/usr/bin/env python3
"""
A program that reads the file it is stored in then computes the frequency of
letters and displays them in a sorted table.  Each time it encounters the
letter 'i', it resumes computation on a generator function that returns
digits if pi.  After a new digit is found, it returns control to the letter
frequency counter.
"""

import sys
from collections import Counter
import time


def generate_pi_digits():
    """
    An unbounded generator that calculates digits of pi using the Gibbons spigot algorithm.
    Every time this function yields, it halts computation and hands control
    back to the caller until the next digit is requested.
    """
    q, r, t, k, n, l = 1, 0, 1, 1, 3, 3
    while True:
        if 4 * q + r - t < n * t:
            time.sleep(0.1*n)
            print(n, end='', flush=True)
            yield n
            nr = 10 * (r - n * t)
            n = ((10 * (3 * q + r)) // t) - 10 * n
            q *= 10
            r = nr
        else:
            nr = (2 * q + r) * l
            nn = (q * (7 * k + 2) + r * l) // (t * l)
            q *= k
            t *= l
            l += 2
            k += 1
            n = nn
            r = nr


def read_source_file(file_path):
    """Step 3: Reads the file this code is stored in."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        sys.exit(1)


def process_characters(source_code, pi_gen):
    """
    Step 4: Processes the file character by character.
    Updates the frequency table and resumes pi computation when 'i' is encountered.
    """
    letter_freq = Counter()
    computed_pi_digits = []

    for char in source_code:
        if char.isalpha():
            letter_freq[char.lower()] += 1

        if char.lower() == "i":
            digit = next(
                pi_gen
            )  # resume pi computation until exactly one new digit is returned
            computed_pi_digits.append(str(digit))

    return letter_freq, computed_pi_digits


def main():
    iter: int = 0
    while True:
        iter += 1
        pi_gen = generate_pi_digits()  # initialize the pi generator

        try:
            current_file_path = __file__
        except NameError:
            print("Error: __file__ is not defined. Please run this as a script.")
            sys.exit(1)

        source_code = read_source_file(current_file_path)
        print(f"Iteration {iter}: Processing source file '{current_file_path}'...")
        letter_freq, computed_pi_digits = process_characters(source_code, pi_gen)
        print()

if __name__ == "__main__":
    main()
