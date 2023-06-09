#!/usr/bin/python3

# This uses newton's method to find the square root of a number.
# It also shows the result using math.sqrt() for comparison.

import math # need this for sqrt()
import sys # need this for exit()

def newton_approx_sqrt(n):
    # This function takes a number n and returns an approximation
    # for sqrt(n). It does this using newton's method.
    guess = 1.0
    print("Starting with ", guess)
    while distance(guess*guess, n) > 0.001:
        guess = better_approx(n, guess)
        print("Next guess is ", guess)
    return guess

def distance(a, b):
    # Returns the distance between a and b
    return abs(b - a)

def better_approx(n, s):
    # This function takes a number n and returns an approximation
    # for sqrt(n), where the argument s is a starting guess.
    # The result will be no worse an approximation than s was.
    p = float(n) / float(s)
    # Now, n equals p times s, so sqrt(n) is somewhere between p and s
    avg = (p + s) / 2.0
    return avg


# The main program...
x = float(input("Please enter a number: "))
if x < 0:
    print("Sorry, this doesn't work for negative numbers")
    sys.exit(0)

s = newton_approx_sqrt(x)
r = math.sqrt(x)

print("Using newton's method, sqrt(x) is about ", s)
print("Using the math module, sqrt(x) is about ", r)

