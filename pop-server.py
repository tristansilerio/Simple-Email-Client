#!/usr/bin/python3

# Author: K. Walsh <kwalsh@cs.holycross.edu>
# Date: 20 August 2020
#
# A simple POP3 server from scratch in Python. Run it like this:
#   sudo ./pop3-server.py
# The "sudo" part is necessary on Linux if using the default port, since that
# port requires root privileges. It may or may not be necessary on Windows or
# MacOS (this code hasn't been tested yet on those platforms).
#
# By default, it will listen on port 110, a privileged port If you want to use a
# different port (e.g. port 12345, which does not require root privileges), you
# can run it like this:
#   ./pop3-server.py 12345
#
# Mailbox files are stored in the ./var_mail/ directory. If you want it to store
# mail in a different directory (e.g. "./Desktop/Stuff"), run it like this:
#   sudo ./pop3-server 110 ./Desktop/MyMailboxes
#
# Any user with a mailbox file can log in with the password "hunter2".
#
# This code is multi-threaded: for each incoming connection from a client, we
# start a separate thread to handle interaction with that client. This means
# there can be multiple concurrent connections being processed at the same time.
# This program has no global variables, though, so this doesn't cause problems.
#
# Note: This code is not "pythonic" at all; there are more concise ways to write
# this code by using python features like dicts and string interpolation. We
# also avoid use of any outside modules except for a few basic ones.

import os          # for os.path.isfile()
import socket      # for socket stuff
import sys         # for sys.argv
import threading   # for threading.Thread()
import re          # for regex split()
import datetime    # for printing timestamps in debug messages
import traceback   # for printing exceptions
import fcntl       # for Posix file locking


# Global constants, with default values.
# Some of these can be overridden with command-line parameters.
server_host = ""        # empty string means "use any available network interface"
server_port = 110       # 110 is the standard POP3 TCP port
mail_dir = "./var_mail" # normally /var/mail/, but this is better for testing


# log() prints a message to the console, for debugging.
# Since multi-threading can jumble up the order of output on the screen, we
# print out the current thread's name on each line of output. We also include a
# timestamp with each message.
def log(debugmsg):
    prefix = str(datetime.datetime.now()) + " " + threading.current_thread().name
    # When printing multiple lines, indent each line a bit
    indent = (" " * len(prefix))
    linebreak = "\n" + indent + ": "
    lines = debugmsg.splitlines()
    debugmsg = linebreak.join(lines)
    # Print it all out.
    print(prefix + ": " + debugmsg)


# recv_one_line() reads data from socket c until a "\r\n" prair is detected.
# It returns all the data received as a python string, not including the
# terminating "\r\n" pair. As an extra server-only debugging feature, this
# function also looks for any stray newline "\n" in the incoming data, and
# immediately stops if one is found. This is because no proper POP3 client
# should ever send a single newline, and should always end a line with a "\r\n"
# pair. This function returns a pair containing the data and an error message.
def read_one_line(c):
    data = ""
    # Keep reading from socket, one byte at a time, until we get a "\r\n" pair.
    while not data.endswith("\r\n"):
        # Check for stray newlines.
        if "\n" in data:
            log("Client sent plain newline, dropping data");
            return (None, "You sent a plain '\\n'. Did you mean to send a '\\r\\n' pair?")
        # Read one more byte from socket, append it to our data.
        try:
            more_data = c.recv(1)
            if not more_data:
                log("Socket connection was lost")
                return (None, None)
            data += more_data.decode() # decode byte as an ascii character
        except:
            log("Error reading from socket: " + traceback.format_exc())
            return (None, None)
    # Return the accumulate data, without the terminating "\r\n" sequence.
    return (data[:-2], None)


# Each POP3 client connection can be in any one these states:
states = [
        "INITIALIZATION", # client has just connected, we will send welcome
        "AUTHORIZATION", # we sent welcome, waiting for USER command
        "AUTHORIZATION (just after USER command)", # got USER, waiting for PASS
        "TRANSACTION", # normal operation, ready to do stuff
        "UPDATE", # after QUIT, mailbox file has been saved
        "FAILED", # after QUIT, mailbox file could not be saved
        ]


# List of valid POP3 commands. For each, list how many arguments it expects, and
# which states it is allowed in.
valid = {
        "QUIT": (None,                   "any"),
        "USER": ("one string",           "AUTHORIZATION"),
        "PASS": ("one string",           "AUTHORIZATION (just after USER command)"),
        "STAT": (None,                   "TRANSACTION"),
        "LIST": ("one optional integer", "TRANSACTION"),
        "RETR": ("one integer",          "TRANSACTION"),
        "DELE": ("one integer",          "TRANSACTION"),
        "NOOP": (None,                   "TRANSACTION"),
        "RSET": (None,                   "TRANSACTION")
        }

# parse_message_number() converts string s into an integer, but also
# performs some sanity checks to ensure it is a valid message number. It
# returns a pair of the integer and an error message (or None if no error).
def parse_message_number(s, msgcount, deletions):
    err = None
    msgno = 0
    try:
        msgno = int(s)
    except:
        log("Rejecting because '%s' is not an integer" % (s))
        err = "You sent '%s', but that is not an integer" % (s)
    if err is None and (msgno <= 0 or msgno > msgcount):
        log("Message number %d is not valid" % (msgno))
        err = "Sorry, message number %d does not exist" % (msgno)
    if err is None and msgno in deletions:
        log("Message number %d is marked for deletion" % (msgno))
        err = "Sorry, message number %d is already marked for deletion" % (msgno)
    return (msgno, err)


# parse_pop3_command() splits a line into keyword and argument parts. It also
# does lots of sanity checking. It returns a 3-tuple containning the keyword, a
# list of arguments (or an emptylist if there were no arguments), and an error
# message (or None if there were no errors).
def parse_pop3_command(line, curstate, msgcount, deletions):
    words = line.split(' ')
    if len(words) == 0:
        return (None, [], "You sent an empty string")
    keyword = words[0].upper()
    args = words[1:]
    n = len(args)
    # Sanity check: make sure keyword is in our list of valid commands
    if keyword not in valid:
        err = "You sent '%s', but that is not a recognized command" % (keyword)
        return (None, [], err)
    (validarg, validstate) = valid[keyword]
    # Sanity check: make sure we are in an appropriate state for that command
    if (curstate != validstate) and (validstate != "any"):
        err = "'%s' only works in %s state, but server is in %s state" % (keyword, validstate, curstate)
        return (None, [], err)
    # Sanity check: make sure none of the arguments are empty strings
    if "" in args:
        err = "You sent an empty argument, e.g. trailing spaces, or adjacent spaces"
        return (None, [], err)
    # Sanity check: make sure we have appropriate number of arguments
    if validarg == None and n != 0:
        err = "%s takes no arguments, but you sent %s of them" % (keyword, n)
        return (None, [], err)
    if validarg == "one string" and n != 1:
        err = "%s takes one string argument, but you sent %s of them" % (keyword, n)
        return (None, [], err)
    if validarg == "one integer" and n != 1:
        err = "%s takes one integer argument, but you sent %s of them" % (keyword, n)
        return (None, [], err)
    if validarg == "one optional integer" and n > 1:
        err = "%s takes one optional integer argument, but you sent %s of them" % (keyword, n)
        return (None, [], err)
    # Sanity check: make integer arguments are valid message numbers
    if n == 1 and (validarg == "one integer" or validarg == "one optional integer"):
        (msgno, err) = parse_message_number(args[0], msgcount, deletions)
        args[0] = msgno
        if err is not None:
            return (None, [], err)
    # Hurray, all checks passed.
    return (keyword, args, None)


# handle_pop3_connection() runs the entire POP3 protocol for a single client
# connection. It sends a greeting, then waits for client messages and responds
# appropriately to those messages.
def handle_pop3_connection(c, client_addr):
    log("Welcoming connection from " + str(client_addr))

    # POP3 is a "stateful" protocol, meaning there are long-lived variables on
    # the server associated with each client connection. When a connection dies,
    # this function returns, and the variables here are discarded. Here are the
    # per-connection variables we need:
    state = "INITIALIZATION" # the state of this connection, i.e. what it is doing
    user = None              # user that has (or started to) login on this connection
    mbox = None              # mailbox of that user, after the password is given
    msgs = []                # list of messages parsed from mbox file  
    deletions = []           # list of message numbers to be deleted

    # POP3 protocol is a greeting, followed by request, response pairs
    try:
        # send the greeting
        c.sendall(b"+OK Welcome to POP3 demo for csci356\r\n")
        state = "AUTHORIZATION"

        while True:
            # wait for one request from the client
            (line, err) = read_one_line(c)
            if err is not None:
                log("Sending error response: " + err)
                c.sendall(("-ERR " + err + "\r\n").encode())
                continue
            if line is None:
                break
            log("Received from client: " + line)
            
            # easter egg: if we get polite request to exit, then do so
            if line == "would you please exit":
                log("Exiting soon.")
                global done
                done = True
                break

            # examine that request, and do something based on it
            (keyword, args, err) = parse_pop3_command(line, state, len(msgs), deletions)

            # if command wasn't recognized at all, just send an error response
            if err is not None:
                log("Sending error response: " + err)
                c.sendall(("-ERR " + err + "\r\n").encode())

            # USER command in AUTHORIZATION state does sanity checks on
            # username, then switches to AUTHORIZATION (just after USER command) state
            elif keyword == "USER":
                user = args[0]
                log("Checking username: " + user)
                # a few sanity checks on username
                if not re.match('^[a-zA-Z]+[0-9]*$', user):
                    log("Rejecting due to suspicious characters")
                    c.sendall(("-ERR Sorry, user name " + user + " looks too suspicious\r\n").encode())
                    user = None
                elif os.path.isfile(mail_dir + "/" + user):
                    log("Username seems legit, now waiting for PASS command")
                    c.sendall(("+OK Hi "+user+", ready for your super secret password\r\n").encode())
                    state = "AUTHORIZATION (just after USER command)"
                else:
                    log("Rejecting because mbox file %s/%s is missing" % (mail_dir, user))
                    c.sendall(("-ERR Sorry, user name " + user + " doesn't seem to have a mailbox\r\n").encode())
                    user = None

            # PASS command in AUTHORIZATION (just after USER command) state checks
            # the password, then switches to TRANSACTION state
            elif keyword == "PASS":
                passwd = args[0]
                log("Checking password: " + passwd)
                if passwd == "hunter2":
                    mbox, err = open_and_lock_mbox(user)
                    if err is None:
                        msgs = parse_mbox(mbox)
                        if msgs is None:
                            err = "Something went wrong when parsing the mbox file"
                            unlock_and_close_mbox(mbox, user, None, None)
                            mbox = None
                            msgs = []
                    if err is None:
                        log("Password accepted, mailbox opened")
                        c.sendall(("+OK nice guess, you are now logged in as "+user+"\r\n").encode())
                        state = "TRANSACTION"
                    else:
                        log("Password accepted, but mailbox could not be opened")
                        c.sendall(("-ERR " + err + "\r\n").encode())
                else:
                    log("Rejecting due to wrong password")
                    c.sendall(("-ERR Sorry, wrong password, be sure to use the fake one\r\n").encode())

            # STAT command in TRANSACTION state returns some statistics to client
            elif keyword == "STAT":
                nn = len(msgs) - len(deletions)
                mm = sum([len(msg[2]) for (i, msg) in enumerate(msgs) if (i+1) not in deletions])
                log("Sending status message for %d messages" % (nn))
                c.sendall(("+OK %d %d\r\n" % (nn, mm)).encode())

            # LIST command in TRANSACTION state lists info about all messages,
            # or if an argument was given, just the one specified message
            elif keyword == "LIST":
                if len(args) == 0:
                    nn = len(msgs) - len(deletions)
                    mm = sum([len(msg[2]) for (i, msg) in enumerate(msgs) if (i+1) not in deletions])
                    log("Sending listing for all %d un-marked messages" % (nn))
                    c.sendall(("+OK listing for %d messages (%d bytes total) follows\r\n" % (nn, mm)).encode())
                    for (i, msg) in enumerate(msgs):
                        if (i+1) not in deletions:
                            c.sendall(("%d %d %s %s\r\n" % (i+1, len(msg[2]), msg[0], msg[1])).encode())
                    c.sendall(b".\r\n")
                else:
                    msgno = args[0]
                    log("Sending info about message %d" % (msgno))
                    msg = msgs[msgno-1]
                    c.sendall(("+OK %d %d %s %s\r\n" % (msgno, len(msg[2]), msg[0], msg[1])).encode())

            # RETR command in TRANSACTION state retrieves one message
            elif keyword == "RETR":
                msgno = args[0]
                msg = msgs[msgno-1]
                log("Sending contents of message %d" % (msgno))
                c.sendall(("+OK message %d (%d bytes total) follows\r\n" % (msgno, len(msg[2]))).encode())
                for line in msg[2].splitlines(False):
                    # if a line starts with "." we must "byte-stuff" an extra
                    # "." at the start, because a lone "." is used to mark the
                    # end of the message
                    if line.startswith("."):
                        line = "." + line
                    c.sendall((line + "\r\n").encode())
                c.sendall(b".\r\n")

            # NOOP command in TRANSACTION state does nothing
            elif keyword == "NOOP":
                log("Nothing to do...")
                c.sendall(b"+OK\r\n")

            # DELE command in TRANSACTION state marks one message as "to be deleted"
            elif keyword == "DELE":
                msgno = int(args[0])
                deletions.append(msgno)
                log("Marked message %d for deletion" % (msgno))
                c.sendall(("+OK message %d marked for deletion\r\n" % (msgno)).encode())

            # RSET command in TRANSACTION state unmarks the "to be deleted" messages
            elif keyword == "RSET":
                n = len(deletions)
                deletions = []
                log("Unmarked %d messages, they will no longer be deleted" % (n))
                c.sendall(("+OK unmarked %d messages previosly marked for deletion\r\n" % (n)).encode())

            # QUIT command in TRANSACTION state saves the mailbox,
            # switches to UPDATE or FAILED state, and closes the connection
            elif keyword == "QUIT" and state == "TRANSACTION":
                try:
                    err = unlock_and_close_mbox(mbox, user, msgs, deletions)
                except:
                    log("Oops, failed to close mbox file: %s" % (traceback.format_exc()))
                    err = "Something went wrong saving mbox file"
                mbox = None
                if err is not None:
                    log("Sending goodbye error message")
                    state = "FAILED"
                    c.sendall(("-ERR" + err + "\r\n").encode())
                else:
                    log("Sending goodbye success response")
                    state = "UPDATE"
                    c.sendall(("+OK goodbye, deleted %d messages, your mailbox is saved\r\n" % (len(deletions))).encode())
                break # stop the loop

            # QUIT command in other states just drops the connection
            elif keyword == "QUIT":
                log("Sending goodbye response")
                c.sendall(b"+OK goodbye, no mailboxes were changed\r\n")
                break # stop the loop

            # We should not get here, every message should be handled above.
            else:
                log("I'm confused, this should not happen")
                c.sendall(("-ERR Sorry, I'm confused\r\n").encode())
    except:
        log("Oops, was in %s state but something went wrong: %s" % (state, traceback.format_exc()))
    finally:
        c.close()
    log("Final state was " + state)
    log("Done with connection from " + str(client_addr))


# open_and_lock_mbox() opens and "locks" a mailbox file. Once locked, the file
# can't be opened again until it is unlocked.
def open_and_lock_mbox(name):
    filename = mail_dir + "/" + name
    mbox = None
    try:
        log("Opening mbox %s" % (filename))
        mbox = open(filename, 'rb+')
    except:
        log("Failed to open mbox %s: %s" % (filename, traceback.format_exc()))
        return (None, "Sorry, problem opening mailbox for user %s" % (name))
    try:
        log("Locking mbox %s" % (filename))
        fcntl.flock(mbox, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except:
        mbox.close()
        log("Failed to lock mbox %s: %s" % (filename, traceback.format_exc()))
        return (None, "Sorry, mailbox for user %s is busy and locked, try another" % (name))
    return (mbox, None)

# unlock_and_close_mbox() "unlocks" and closes a mailbox file. If msgs and
# deletions are not None, it also saves the messages before closing the file.
def unlock_and_close_mbox(mbox, name, msgs, deletions):
    filename = mail_dir + "/" + name
    err = None
    if msgs is not None and deletions is not None and len(deletions) > 0:
        log("Saving modified mbox %s" % (filename))
        try:
            mbox.seek(0, 0)
            mbox.truncate()
            for (i, msg) in enumerate(msgs):
                if (i+1) not in deletions:
                    if i > 0:
                        mbox.write(b"\n")
                    mbox.write(("From " + msg[0] + "\n").encode())
                    for line in msg[2].splitlines(False):
                        line = re.sub('^>(>*From )', '\1', line)
                    mbox.write((line + "\n").encode())
        except:
            log("Failed to properly save mbox: %s" % (traceback.format_exc()))
            err = "Sorry, the mailbox could not be saved, it might be corrupt now"
    log("Unlocking mbox %s" % (filename))
    # unlock is not necessary, as the lock is released when file is closed
    # try:
    #     fcntl.flock(mbox, fcntl.LOCK_UN)
    # except:
    #     log("Failed to unlock mbox: %s" % (traceback.format_exc()))
    #     if err is None:
    #         err = "Sorry, the mailbox could not be unlocked"
    try:
        mbox.close()
    except:
        log("Failed to close mbox: %s" % (traceback.format_exc()))
        if err is None:
            err = "Sorry, the mailbox could not be properly closed"
    return err

# parse_mbox() parses the user's mailbox file and returns a python list of
# [source, subject, message] triplets. The source is usually something like
# "someone@example.com". The subject is a string like "SubjecT: hi there" taken
# from the email, or it may an empty string. The message is a string, usually
# containing SMTP email headers and the contents of the email message.
#
# Each mbox file contains one user's mail. The mbox format is just a 
# concatenation of all the user's email messages, with each message
# preceded by a blank line and a line like "From someone@example.com".
# The message itself is usually a bunch of SMTP headers, followed by
# the contents of the message.
def parse_mbox(mbox):
    try:
        msgs = []
        # Split the entire file into lines, and process each
        # line one at a time. Don't keep the line endings.
        mbox.seek(0, 0)
        lines = mbox.read().splitlines(False)
        prevblank = True
        for line in lines:
            line = line.decode() # convert from bytes to python string
            # Look for the start of a new message
            if prevblank and line.startswith("From "):
                msgfrom = line[5:].strip()
                msgsubj = ""
                msgbody = ""
                msgs.append([msgfrom, msgsubj, msgbody])
                prevblank = False
            # Ignore anything before the first "From " line
            elif len(msgs) == 0:
                prevblank = re.match('^$', line)
            else:
                # A previously-seen blank line was followed by something
                # other than "From ", so it should have been part of the
                # message. Add it now.
                if prevblank:
                    msgs[-1][2] += "\r\n"
                    prevblank = False
                # Check whether we found a blank line or part of message.
                if re.match('^$', line):
                    prevblank = True
                else:
                    line = re.sub('^(>*From )', '>\1', line)
                    msgs[-1][2] += line + "\r\n"
                    #if line.startswith("Subject: ") and msgs[-1][1] == "":
                    #    msgs[-1][1] = line.strip()
        # A previously-seen blank line was followed by end of file,
        # so it should have been part of the last message. Add it now.
        if prevblank and len(msgs) > 0:
            msgs[-1][2] += "\r\n"
            prevblank = False
        # All lines of mbox file have been examined.
        # Print out a summary (just for debug purposes) and
        # return the list of (source, message) pairs.
        return msgs
    except:
        log("Problem reading mailbox file: " + traceback.format_exc())
        return None

# print_mailbox_stats() just prints some statistics, useful for debugging.
def print_mailbox_stats(user):
    mbox, err = open_and_lock_mbox(user)
    if err is not None:
        log(err)
        return None
    msgs = parse_mbox(mbox)
    if msgs is not None:
        nn = len(msgs)
        mm = sum([len(msg[2]) for msg in msgs])
        log("%s has %d messages with a total of %d bytes" % (name, nn, mm))
    unlock_and_close_mbox(mbox, user, None, None)


#######################################################################
# This remainder of this file is the main program


# Get command-line parameters, if present
if len(sys.argv) >= 4:
    print("Sorry, this program only accepts 0, 1 or 2 arguments.")
    print("Usage: %s [port [maildir]]" % sys.argv[0])
    sys.exit(1)
if len(sys.argv) >= 2:
    server_port = int(sys.argv[1])
if len(sys.argv) >= 3:
    mail_dir = sys.argv[2]


# Print a welcome message.
server_addr = (server_host, server_port)
log("Starting POP3 server")
log("Listening on address %s" % (str(server_addr)))
log("Serving mailbox files from %s" % (mail_dir))

# Do a quick scan of the mail directory, just to see which mbox files are
# present and how big they are. This is just a sanity check, for debugging.
for name in os.listdir(mail_dir):
    if os.path.isfile(mail_dir + "/" + name) and not name[:-1].endswith(".sw"):
        print_mailbox_stats(name)


# Create the server socket, and set it up to listen for connections
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(server_addr)
s.listen(5)

# Finally, we repeatedly accept and process connections from clients
log("==== Ready for connections ====")
done = False
try:
    while not done:
        c, client_addr = s.accept()
        t = threading.Thread(target=handle_pop3_connection, args=(c,client_addr))
        t.daemon = True
        t.start()
finally:
    log("==== Server is shutting down ====")
    s.close()

