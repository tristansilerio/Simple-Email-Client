#!/usr/bin/python3
# Author: Tristan Silerio
# Date: 15 September 2022
#
# A simple POP3 email client from scratch in Python. Run it like this:
#   ./email-client.py "User Name"
#
# It will connect to port 110, the standard POP3 port, by default. If you want
# to use a different port (e.g. port 12345), you can run it like this:
#  
# This funs a simple "email" client for the user to look at their messages. 
# They are give the options to read, delete, or skip the message they are viewing. 

# Imported things from pop-server.py
from ast import AsyncFunctionDef
from asyncore import loop, read
from email import message
import numbers
from operator import contains
import os          # for os.path.isfile()
import socket      # for socket stuff
import sys
from tabnanny import check         # for sys.argv
import threading   # for threading.Thread()
import re          # for regex split()
import datetime    # for printing timestamps in debug messages
import traceback   # for printing exceptions
import fcntl       # for Posix file locking


# Global configuration variables, with default values
server_host = "enron.kwalsh.org" 
server_port = 110

# Code taken from pop-client.py 
def read_one_line(c):
    data = ""
    # Keep reading from socket until we get a "\r\n" pair.
    while not data.endswith("\r\n"):
        # Read one more byte from socket, append it to our data.
        try:
            more_data = c.recv(1)
            if not more_data:
                print("Socket connection was lost")
                return None
            data += more_data.decode() # decode byte as an ascii character
        except:
            print("Error reading from socket: " + traceback.format_exc())
            return None
    # Return the accumulate data, without the terminating "\r\n" sequence.
    return data[:-2]


# Get command-line parameters, if present
if len(sys.argv) < 1:
    print("Sorry, this program only accepts 1 argument.")
    print("Usage: %s address [port]" % sys.argv[0])
    sys.exit(1)
user_name = sys.argv[1]



# Print a welcome message
print("Starting POP3 client")
print("Connecting to server %s on port %d" % (server_host, server_port))

# Create a client socket, and connect it to the server
server_addr = (server_host, server_port)
c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
c.connect(server_addr)

# Log in the user given the user input 

def logging_in(user):
    cmd = "USER %s"%user    # assign user input to USER command
    cmd2 = "PASS hunter2"   # fixed password command
    cmd3 = "LIST"           # list command for later 

    err = "ERR"
    #print(cmd)
    c.sendall((cmd + "\r\n").encode()) # first 
    
    resp1 = read_one_line(c)           # get response from server
    resp1 = read_one_line(c)           # and skip one of the lines
    
    if err in resp1:                                    # check if -ERR is in the message
        print("Failed. Server error was: %s"%resp1)     # if so, EXIT 
        sys.exit(1)

    # print it
    elif resp1 is not None:                             
    #print("Response: " + resp)
        c.sendall((cmd2 + "\r\n" ).encode())           # Enter PASS hunter2 to log in  
        resp2 = read_one_line(c)
        if err in resp2:                               # Check if -ERR is in the message
            print("Failed. Server error was: %s"%resp1)
            sys.exit(1)

# Print the Messages
def printMessage():
    #message = read_one_line(c)
    while True:
        message = read_one_line(c)
        print(message)
        if message is ".":
            break

# Delete via POP3 and ask the user to confirm
def confirm_delete(n):
    confirmation = input("Are you sure you want to delete this message?(y/n)")
    if confirmation is 'y':
        c.sendall(("DELE %u"%n+ "\r\n" ).encode())  
        print("Message %u marked for deletion in mailbox!"%(n))
        delete_message = read_one_line(c) # skip the delete message

# Get the mailbox stats regarding the amount of messages 
def mailbox_info(): 
    c.sendall(("STAT"+ "\r\n" ).encode()) 
    mailbox = read_one_line(c)
    #print(mailbox)
    stats = mailbox.split(" ")[1]
    #print("meowww",stats)
    if stats is "'STAT'":
        sys.exit(1)
    elif stats is '0':
        print("You have %s messages!"%stats)
        sys.exit(1) 
    else:
        print("You have %s messages!"%stats)
        return int(stats)

# Lists the message of a giving message number and returns the message
def get_message(box_number):
    c.sendall(("LIST %u"%box_number + "\r\n").encode())
    #print("MEOW!")
    mail = read_one_line(c)
    return mail 

# Check if the messages have all been read 
def check_if_done(p): 
    if (p+1) == mail_amount:  
        return True
    else:
        return False
# Finally, the main user-interaction loop.
try:
    # Server sends a greeting first thing, so receive that and print it
    print("Connected!  Welcome to POP3 demo for csci356")
    print("Logging in to server as user %s with default password." %user_name)

    logging_in(user_name)               # Log the user in, if the user can 
    done = False                        # boolean to keep track if the user is done
    loop_check = 0                      # counter for amount of loops to increment loop values
    delete_counter = 0                  # track how many messages are to be deleted
    mail_amount = int(mailbox_info())   # store the number of messages into an integer
    

    # Next, repeatedly get user input and send it to the server,
    # then print whatever response the server sends back.
    while True:
        inp = input("Type 'q' at any time to quit, or hit enter to see the list of messages.\r\n")
        if inp is 'q': # quit 
            break
        else:
            i = (5 * loop_check) # view the messages 5 at a time
            j = (5 * loop_check) # asking the user about messages 5 at a time
            #print(i, loop_check)
            for i in range(i, i+5): # print the emails in this first loop, but ONLY 5 at a time
                emails = get_message(i+1)
                emails = emails[5:]
                print("[%u] %s"%(i+1,emails))

            for j in range(j, j+5): # Now, cycle through those messages one at a time, asking the user whether or not to read, delete, or skip
                readSkipDelete = input("Do you want to (r)ead, (d)elete, or (s)kip message %u\r\n"%(j+1))
                if readSkipDelete is 'r': # if user wants to read message
                    c.sendall(("RETR %u"%(j+1) + "\r\n" ).encode())
                    print("[start of message] %u"%(j+1))
                    printMessage()
                    deleteOrSkip = input("Do you want to (d)elete, or (s)kip message %u\r\n"%(j+1))
                    if  deleteOrSkip is 'd': # if user is sure that they want to delete message
                        confirm_delete(j+1)
                        delete_counter = delete_counter + 1
                        if check_if_done(j):
                            done = True
                            break
                    else: 
                        if check_if_done(j):
                            done = True
                            break
                        continue
                elif readSkipDelete is 'd': # if the user wants to delete 
                    confirm_delete(j+1)
                    delete_counter = delete_counter + 1
                    if check_if_done(j):
                        done = True
                        break
                elif readSkipDelete is 's': # if the user wants to skip 
                    if check_if_done(j):
                        done = True
                        #print(done)
                        break
                    else: # continue reading the messages
                        continue 
                elif readSkipDelete is 'q': # if the user wants to quit at any time
                    done = True
                    break 
                else: 
                    print("Try again clicking the correct keys: r, d, s, or q :)") # exit if they do not put a readable key
                    sys.exit(1)   
            if done: # if done = TRUE, then break out of loop and give last messages
                break 
            loop_check = loop_check + 1
    
    ## 
    ## Let the user know what he/she has marked for deletion and give them the choice to delete or 
    ## not delete them. Then, quit. 
    if delete_counter > 0: # Only ask if the user has messages to delete
        print("You have %u messages marked for deletion!"%delete_counter) 
        yes_or_no = input("Do you want to delete the messages you marked for deletion?(y/n)") # confirm with user to delete messages
        if yes_or_no is 'y': 
            print("You deleted %u messages!"%delete_counter)
            c.sendall(("QUIT" + "\r\n").encode())           # actually delete the messages
            quit = read_one_line(c)
            print(quit)
        else: 
            print("[%u messages unmarked for deletion]"%delete_counter) 
            c.sendall(("RSET" + "\r\n").encode())           # unmark the messages that are supposed to be deleted 
            ending = read_one_line(c)
    
    print("You have gone through all of your messages! Goodbye :)") # Goodbye statement. 
                          
finally:   
    
    print("Closing socket connection to server")
    c.close()

print("Done") #End

