#!/usr/bin/python3
# Tristan Silerio
# This program just shows off things you can do with lists in python
# 
# a list of numbers
numbers = [1, 5, 10, 25]

# a list of strings
names = ["Alice", "Ada", "Grace"]

# You can print lists
print(numbers)
print(names)

# You can do a traditional counting loop
n = len(numbers) # length of list
for i in range(0, n):
    numbers[i] = numbers[i] + 1
print(numbers)

# Or, you can loop over the elements of a list more easily like this
for x in names:
    print("Hello", x)

# printf-style printing is allowed like this
n = len(names)
print("The %d names, %s, %s, and %s, are all famous in CS." % (n, names[0], names[1], names[2]))

# You can add, remove, sort, etc.
names.append("Alan")
names.sort()
print(names)

