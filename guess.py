#!/usr/bin/python3

import random

secret = random.randint(1, 20)

# use raw_input for unintepreted strings
name = input("What is your name? ")

wrong_guesses = [] # an empty array

while True:
    # use input for values like floats and integers
    x = int(input(name + ", please guess a number between 1 and 20: "))

    if x == secret:
        print("Correct!")
        break
    else:
        print("Sorry, try again...")
        wrong_guesses.append(x)

print("You made %d incorrect guesses!" % (len(wrong_guesses)))
sum = 0
for x in wrong_guesses:
    sum = sum + x
print("The sum of all your wrong guesses is", sum)
