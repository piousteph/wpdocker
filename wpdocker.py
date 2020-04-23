#!/usr/bin/python

import sys
import os
import importlib
import subprocess
import shutil
import time
from datetime import datetime

def showUsage():
    print("Usage:\npython {} action projectName [param1]".format(sys.argv[0]))
    print("Action: create    : Create new project")
    print("        start     : Start project")
    print("        stop      : Stop project")
    print("        delete    : Delete project")
    print("        importdb  : Import database")
    print("        exportdb  : Export database")
    print("        import    : Import wp files")
    print("        export    : Export wp files")
    exit(0)

def manageParameters():
    if(len(sys.argv) < 3):
        print("Missing parameters")
        showUsage()
    elif(sys.argv[1] == "create"):
        createProject(sys.argv[2])
    elif(sys.argv[1] == "start"):
        startProject(sys.argv[2])
    elif(sys.argv[1] == "stop"):
        stopProject(sys.argv[2])
    elif(sys.argv[1] == "delete"):
        deleteProject(sys.argv[2])
    elif(sys.argv[1] == "importdb" and len(sys.argv) == 4):
        importDB(sys.argv[2], sys.argv[3])
    elif(sys.argv[1] == "exportdb"):
        exportDB(sys.argv[2])
    else:
        print("Wrong action")
        showUsage()

def saveProject(name, siteurl, dbname, dbuser, dbpassword, initialized):
    file = open("./" + name + "/settings.py","w") 
    file.write("initialized = " + str(initialized) + "\n")
    file.write("siteurl = \"" + siteurl + "\"\n")
    file.write("database = dict(\n")
    file.write("    name = \"" + dbname + "\",\n")
    file.write("    user = \"" + dbuser + "\",\n")
    file.write("    password = \"" + dbpassword + "\"\n")
    file.write(")\n")
    file.close()


def createProject(name):
    if(os.path.isdir("./" + name)):
        print("Project already exist, please choose another name or start it with command: python {} start {}".format(sys.argv[0], name))
        exit(0)
    
    print("Wordpress setting")
    siteurl = str(input("== site url: "))
    print("")
    print("Database settings")
    dbname = str(input("== DB name: "))
    dbuser = str(input("== User name: "))
    dbpassword = str(input("== Password: "))
    print("Creating directories")
    os.makedirs(name)
    os.makedirs(name + "/database")
    os.makedirs(name + "/html")
    print("Creating settings")
    saveProject(name, siteurl, dbname, dbuser, dbpassword, 0)
    print("Ready to start with command: python {} start {}".format(sys.argv[0], name))

def startProject(name):

    if(os.path.isdir("./" + name) == False):
        print("Project does not exist, please choose another name or create it with command: python {} create {}".format(sys.argv[0], name))
        exit(0)

    if(os.path.isfile("./" + name + "/settings.py") == False):
        print("Project error, cannot continue")
        exit(0)

    settingsFile = "./" + name + "/settings"
    settings = importlib.import_module(".settings", package = name)

    dockerdbargs = []
    if(settings.initialized == 0):
        dockerdbargs = ["docker", "run", 
            "-e", "MYSQL_ROOT_PASSWORD=docker", 
            "-e", "MYSQL_USER=" + settings.database["user"], 
            "-e", "MYSQL_PASSWORD=" + settings.database["password"], 
            "-e", "MYSQL_DATABASE=" + settings.database["name"], 
            "-v", os.getcwd() + "/" + name + "/database:/var/lib/mysql",
            "--name", name + "-db",
            "-d", "mariadb"]
        saveProject(name, settings.siteurl, settings.database["name"], settings.database["user"], settings.database["password"], 1)

        dockerwpargs = ["docker", "run",
            "-e", "WORDPRESS_DB_USER=" + settings.database["user"], 
            "-e", "WORDPRESS_DB_PASSWORD=" + settings.database["password"], 
            "-e", "WORDPRESS_DB_NAME=" + settings.database["name"],
            "-p", "8081:80",
            "-v", os.getcwd() + "/" + name + "/html:/var/www/html",
            "--link", name + "-db:mysql",
            "--name", name + "-wp",
            "-d", "wordpress"]
    else:
        dockerdbargs = ["docker", "start", name + "-db"]
        dockerwpargs = ["docker", "start", name + "-wp"]

    print("Starting DB\n" + ' '.join(dockerdbargs))
    os.system(' '.join(dockerdbargs))

    print("Starting WP\n" + ' '.join(dockerwpargs))
    os.system(' '.join(dockerwpargs))

    print("Waiting 10 seconds for wp starting")
    time.sleep(10)
    # print("Settings rights")
    # os.system("sudo chown -R docker " + os.getcwd() + "/" + name + "/html")

def stopProject(name):
    if(os.path.isdir("./" + name) == False):
        print("Project does not exist, please choose another name or create it with command: python {} create {}".format(sys.argv[0], name))
        exit(0)
    
    dockerdbargs = ["docker", "stop", name + "-db"]
    dockerwpargs = ["docker", "stop", name + "-wp"]

    print("Stoping WP\n" + ' '.join(dockerwpargs))
    os.system(' '.join(dockerwpargs))

    print("Stoping DB\n" + ' '.join(dockerdbargs))
    os.system(' '.join(dockerdbargs))

def deleteProject(name):
    if(os.path.isdir("./" + name) == False):
        print("Project does not exist, please choose another name")
        exit(0)

    stopProject(name)
    dockerdbargs = ["docker", "container", "rm", name + "-db"]
    dockerwpargs = ["docker", "container", "rm",  name + "-wp"]

    print("Removing WP\n" + ' '.join(dockerwpargs))
    os.system(' '.join(dockerwpargs))

    print("Removing DB\n" + ' '.join(dockerdbargs))
    os.system(' '.join(dockerdbargs))

    os.system("sudo chown -R docker " + os.getcwd() + "/" + name + "/database")

    print("Deleting files")
    shutil.rmtree(os.getcwd() + "/" + name)

def importDB(name, file):
    if(os.path.isdir("./" + name) == False):
        print("Project does not exist, please choose another name or create it with command: python {} create {}".format(sys.argv[0], name))
        exit(0)

    if(os.path.isfile("./" + name + "/settings.py") == False):
        print("Project error, cannot continue")
        exit(0)

    if(os.path.isfile(file) == False):
        print("Dumpfile not found, cannot continue")
        exit(0)

    settingsFile = "./" + name + "/settings"
    settings = importlib.import_module(".settings", package = name)

    dockerdbargs = ["docker", "exec", name + "-db", "mysql", 
        "--user=" + settings.database["user"], "--password=" + settings.database["password"], settings.database["name"],
        "<", file]

    print("Importing DB\n" + ' '.join(dockerdbargs))
    os.system(' '.join(dockerdbargs))

def exportDB(name):
    if(os.path.isdir("./" + name) == False):
        print("Project does not exist, please choose another name or create it with command: python {} create {}".format(sys.argv[0], name))
        exit(0)

    if(os.path.isfile("./" + name + "/settings.py") == False):
        print("Project error, cannot continue")
        exit(0)

    settingsFile = "./" + name + "/settings"
    settings = importlib.import_module(".settings", package = name)

    dockerdbargs = ["docker", "exec", name + "-db", "mysqldump", 
        "--user=" + settings.database["user"], "--password=" + settings.database["password"], "--databases", settings.database["name"],
        ">", os.getcwd() + "/" + name + "/" + name + "-dump-" + datetime.today().strftime('%Y%m%d') + ".sql"]

    print("Exporting DB\n" + ' '.join(dockerdbargs))
    os.system(' '.join(dockerdbargs))

manageParameters()