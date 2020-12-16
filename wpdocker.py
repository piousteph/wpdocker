#!/usr/bin/python

import sys
import os
import io
import importlib
import subprocess
import shutil
import time
import hashlib
from python_hosts import Hosts, HostsEntry
from datetime import datetime

def pullwpversion(version):
    osargs = ["docker", "image", "ls"]
    subresult = io.StringIO(subprocess.check_output(osargs).decode())
    for v in subresult:
        if v[0:9] == "wordpress" and v.find(" " + version + " ") > 1:
            return
    print("Requested version not found, trying to pull wordpress version " + version)
    osargs = ["docker", "pull", "wordpress:" + version]
    res = os.system(' '.join(osargs))
    if res == 0:
        return True
    return False

def showUsage():
    print("Usage:\npython {} action projectName [param1]".format(sys.argv[0]))
    print("Action: create    : Create new project")
    print("        start     : Start project")
    print("        stop      : Stop project")
    print("        delete    : Delete project")
    print("        importdb  : Import database")
    print("        exportdb  : Export database")
    print("        md5       : Generate md5 hash for wordpress files")
    print("        diff      : Show changed files since last md5 calculation")
    # print("        import    : Import wp files")
    # print("        export    : Export wp files")
    exit(0)

def manageParameters():
    if len(sys.argv) < 3:
        print("Missing parameters")
        showUsage()
    elif sys.argv[1] == "create":
        createProject(sys.argv[2])
    elif sys.argv[1] == "start":
        startProject(sys.argv[2])
    elif sys.argv[1] == "stop":
        stopProject(sys.argv[2])
    elif sys.argv[1] == "delete":
        deleteProject(sys.argv[2])
    elif sys.argv[1] == "importdb" and len(sys.argv) == 4:
        importDB(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "exportdb":
        exportDB(sys.argv[2])
    elif sys.argv[1] == "md5":
        calcMD5(sys.argv[2])
    elif sys.argv[1] == "diff":
        diff(sys.argv[2])
    else:
        print("Wrong action")
        showUsage()
    
def saveProject(name, siteurl, wpversion, dbhost, dbname, dbuser, dbpassword, initialized):
    file = open("./" + name + "/settings.py","w")
    file.write("initialized = " + str(initialized) + "\n")
    file.write("siteurl = \"" + siteurl + "\"\n")
    file.write("wpversion = \"" + wpversion + "\"\n")
    file.write("database = dict(\n")
    file.write("    host = \"" + dbhost + "\",\n")
    file.write("    name = \"" + dbname + "\",\n")
    file.write("    user = \"" + dbuser + "\",\n")
    file.write("    password = \"" + dbpassword + "\"\n")
    file.write(")\n")
    file.close()

    file = open("./" + name + "/proxy.conf","w")
    file.write("server {\n")
    file.write("    listen 80;\n")
    file.write("    server_name " + siteurl + " www." + siteurl + ";\n")
    file.write("    return 301 https://$server_name$request_uri;\n")
    file.write("}\n")
    file.write("server {\n")
    file.write("    listen 443 ssl;\n")
    file.write("    ssl_certificate /etc/nginx/ssl/localhost.crt;\n")
    file.write("    ssl_certificate_key /etc/nginx/ssl/localhost.key;\n")
    file.write("    ssl_protocols TLSv1.2;\n")
    file.write("    client_max_body_size 0;\n")
    file.write("    server_name " + siteurl + " www." + siteurl + ";\n")
    file.write("    access_log " + os.getcwd() + "/" + name + "/logs/access.log;\n")
    file.write("    error_log " + os.getcwd() + "/" + name + "/logs/error.log;\n")
    file.write("    location / {\n")
    file.write("        proxy_pass http://localhost:8081;\n")
    file.write("        proxy_set_header Host $host;\n")
    file.write("        proxy_set_header X-Real-IP $remote_addr;\n")
    file.write("        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n")
    file.write("        proxy_set_header X-Forwarded-Proto $scheme;\n")
    file.write("        proxy_read_timeout 90;\n")
    file.write("    }\n")
    file.write("}\n")
    file.close()

    file = open("./" + name + "/uploads.ini","w")
    file.write("file_uploads = On\n")
    file.write("memory_limit = 500M\n")
    file.write("upload_max_filesize = 500M\n")
    file.write("post_max_size = 500M\n")
    file.write("max_execution_time = 600\n")
    file.close()

def createProject(name):
    if os.path.isdir("./" + name):
        print("Project already exist, please choose another name or start it with command: python {} start {}".format(sys.argv[0], name))
        exit(0)
    
    print("Wordpress setting")
    siteurl = str(input("== site url: "))
    print("")
    print("Wordpress settings")
    wpversion = str(input("== WP version: "))
    print("Database settings")
    dbhost = str(input("== DB host: "))
    dbname = str(input("== DB name: "))
    dbuser = str(input("== User name: "))
    dbpassword = str(input("== Password: "))
    print("Creating directories")
    os.makedirs(name)
    os.makedirs(name + "/database")
    os.makedirs(name + "/html")
    os.makedirs(name + "/logs")
    print("Creating settings")
    saveProject(name, siteurl, wpversion, dbhost, dbname, dbuser, dbpassword, 0)
    print("Ready to start with command: python {} start {}".format(sys.argv[0], name))

def startProject(name):

    if os.path.isdir("./" + name) == False:
        print("Project does not exist, please choose another name or create it with command: python {} create {}".format(sys.argv[0], name))
        exit(0)

    if os.path.isfile("./" + name + "/settings.py") == False:
        print("Project error, cannot continue")
        exit(0)

    settingsFile = "./" + name + "/settings"
    settings = importlib.import_module(".settings", package = name)

    dockerdbargs = []
    if settings.initialized == 0:
        if pullwpversion(settings.wpversion) == False:
            print("Error while getting requested wordpress version, available version can be found https://wordpress.org/download/releases/")
            print("Start aborted")
            exit(-1)

        saveProject(name, settings.siteurl, settings.wpversion, settings.database["host"], settings.database["name"], settings.database["user"], settings.database["password"], 1)
        
        dockerdbargs = ["docker", "run", 
            "-e", "MYSQL_ROOT_PASSWORD=docker", 
            "-e", "MYSQL_USER=" + settings.database["user"], 
            "-e", "MYSQL_PASSWORD=" + settings.database["password"], 
            "-e", "MYSQL_DATABASE=" + settings.database["name"], 
            "-v", os.getcwd() + "/" + name + "/database:/var/lib/mysql",
            "--name", name + "-db",
            "-d", "mariadb"]

        if settings.database["host"]:
            dockerdbargs[10:10] = ["-h", settings.database["host"]]

        

        dockerwpargs = ["docker", "run",
            "-e", "WORDPRESS_DB_USER=" + settings.database["user"], 
            "-e", "WORDPRESS_DB_PASSWORD=" + settings.database["password"], 
            "-e", "WORDPRESS_DB_NAME=" + settings.database["name"],
            "-p", "8081:80",
            "-v", os.getcwd() + "/" + name + "/html:/var/www/html",
            "-v", os.getcwd() + "/" + name + "/uploads.ini:/usr/local/etc/php/conf.d/uploads.ini",
            "--link", name + "-db:mysql",
            "--name", name + "-wp",
            "-d", "wordpress:" + settings.wpversion]

        if settings.database["host"]:
            dockerwpargs[2:2] = ["-e", "WORDPRESS_DB_HOST=" + settings.database["host"]]

    else:
        dockerdbargs = ["docker", "start", name + "-db"]
        dockerwpargs = ["docker", "start", name + "-wp"]

    print("Starting DB\n" + ' '.join(dockerdbargs))
    os.system(' '.join(dockerdbargs))

    print("Starting WP\n" + ' '.join(dockerwpargs))
    os.system(' '.join(dockerwpargs))

    print("Waiting 10 seconds for wp starting")
    time.sleep(10)

    print("Setting rights")
    osargs = ["sudo", "chown", "-R", "docker:docker",  os.getcwd() + "/" + name + "/html"]
    os.system(' '.join(osargs))
    osargs = ["sudo", "chown", "-R", "docker:www-data",  os.getcwd() + "/" + name + "/html/wp-content"]
    os.system(' '.join(osargs))
    osargs = ["sudo", "chmod", "-R", "775",  os.getcwd() + "/" + name + "/html/wp-content"]
    os.system(' '.join(osargs))

    print("Setting host")
    osargs = ["sudo", "chmod", "666", "/etc/hosts"]
    os.system(' '.join(osargs))
    my_hosts = Hosts()
    site_urls = [settings.siteurl, " www." + settings.siteurl]
    if settings.database["host"] != "127.0.0.1" or settings.database["host"] != "localhost":
        site_urls.append(settings.database["host"])
    new_entry = HostsEntry(entry_type="ipv4", address="127.0.0.1", names=site_urls)
    my_hosts.add([new_entry])
    my_hosts.write()
    osargs = ["sudo", "chmod", "644", "/etc/hosts"]
    os.system(' '.join(osargs))

    print("Setting proxy")
    osargs = ["sudo", "cp", os.getcwd() + "/" + name + "/proxy.conf", "/etc/nginx/sites-available/wordpress"]
    os.system(' '.join(osargs))
    osargs = ["sudo", "systemctl", "restart", "nginx"]
    os.system(' '.join(osargs))

    print("Website successfully started")
    print("Web site is accessible at https://" + settings.siteurl + " or https://www." + settings.siteurl + "\n")
    print("** If you have a redirection loop, please add to wp_config.php the following lines at the begin of file\n")
    print("if (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https') {")
    print("    $_SERVER['HTTPS'] = 'on';")
    print("}")
    print("")
    print("** To enable direct update, please add to wp_config.php the following lines at the begin of file\n")
    print("define('FS_METHOD', 'direct');")
    print("")

def stopProject(name):
    if os.path.isdir("./" + name) == False:
        print("Project does not exist, please choose another name or create it with command: python {} create {}".format(sys.argv[0], name))
        exit(0)
    
    settingsFile = "./" + name + "/settings"
    settings = importlib.import_module(".settings", package = name)

    dockerdbargs = ["docker", "stop", name + "-db"]
    dockerwpargs = ["docker", "stop", name + "-wp"]

    print("Stoping WP\n" + ' '.join(dockerwpargs))
    os.system(' '.join(dockerwpargs))

    print("Stoping DB\n" + ' '.join(dockerdbargs))
    os.system(' '.join(dockerdbargs))

    print("Restore rights")
    osargs = ["sudo", "chown", "-R", "docker:docker",  os.getcwd() + "/" + name + "/html/wp-content"]
    os.system(' '.join(osargs))
    osargs = ["sudo", "chmod", "-R", "755",  os.getcwd() + "/" + name + "/html/wp-content"]
    os.system(' '.join(osargs))

    print("Clear host")
    osargs = ["sudo", "chmod", "666", "/etc/hosts"]
    os.system(' '.join(osargs))
    my_hosts = Hosts()
    my_hosts.remove_all_matching(name=settings.siteurl)
    my_hosts.write()
    osargs = ["sudo", "chmod", "644", "/etc/hosts"]
    os.system(' '.join(osargs))

def deleteProject(name):
    if os.path.isdir("./" + name) == False:
        print("Project does not exist, please choose another name")
        exit(0)

    stopProject(name)
    dockerdbargs = ["docker", "container", "rm", name + "-db"]
    dockerwpargs = ["docker", "container", "rm",  name + "-wp"]

    print("Removing WP\n" + ' '.join(dockerwpargs))
    os.system(' '.join(dockerwpargs))

    print("Removing DB\n" + ' '.join(dockerdbargs))
    os.system(' '.join(dockerdbargs))

    osargs = ["sudo", "chown", "-R", "docker", os.getcwd() + "/" + name + "/database"]
    os.system(' '.join(osargs))

    print("Deleting files")
    shutil.rmtree(os.getcwd() + "/" + name)

def importDB(name, file):
    if os.path.isdir("./" + name) == False:
        print("Project does not exist, please choose another name or create it with command: python {} create {}".format(sys.argv[0], name))
        exit(0)

    if os.path.isfile("./" + name + "/settings.py") == False:
        print("Project error, cannot continue")
        exit(0)

    if os.path.isfile(file) == False:
        print("Dumpfile not found, cannot continue")
        exit(0)

    # if file[-3:] == ".gz":
    #     os.system("tar -xvzf " + file)

    settingsFile = "./" + name + "/settings"
    settings = importlib.import_module(".settings", package = name)

    dockerdbargs = ["docker", "exec", "-i", name + "-db", "mysql", 
        "--user=" + settings.database["user"], "--password=" + settings.database["password"], settings.database["name"],
        "<", file]

    print("Importing DB\n" + ' '.join(dockerdbargs))
    os.system(' '.join(dockerdbargs))

def exportDB(name):
    if os.path.isdir("./" + name) == False:
        print("Project does not exist, please choose another name or create it with command: python {} create {}".format(sys.argv[0], name))
        exit(0)

    if os.path.isfile("./" + name + "/settings.py") == False:
        print("Project error, cannot continue")
        exit(0)

    settingsFile = "./" + name + "/settings"
    settings = importlib.import_module(".settings", package = name)

    dockerdbargs = ["docker", "exec", name + "-db", "mysqldump", 
        "--user=" + settings.database["user"], "--password=" + settings.database["password"], "--databases", settings.database["name"],
        ">", os.getcwd() + "/" + name + "/" + name + "-dump-" + datetime.today().strftime('%Y%m%d') + ".sql"]

    print("Exporting DB\n" + ' '.join(dockerdbargs))
    os.system(' '.join(dockerdbargs))

def calcMD5(name):
    if os.path.isdir("./" + name) == False:
        print("Project does not exist, please choose another name or create it with command: python {} create {}".format(sys.argv[0], name))
        exit(0)
    
    md5 = ""

    for subdirectories, directories, files in os.walk("./" + name + '/html'):
        for file_name in files:
            file_loc = subdirectories + os.path.sep + file_name
            md5 = md5 + file_loc + ":" + hashlib.md5(open(file_loc,'rb').read()).hexdigest() + "\n"

    file = open("./" + name + "/wp.md5","w")
    file.write(md5)
    file.close()
    
def diff(name):
    if os.path.isdir("./" + name) == False:
        print("Project does not exist, please choose another name or create it with command: python {} create {}".format(sys.argv[0], name))
        exit(0)

    if os.path.isfile("./" + name + "/wp.md5") == False:
        print("no MD5 reference, please generate one")
        exit(0)


    md5file = open("./" + name + "/wp.md5", "r")
    curmd5 = md5file.readlines()
    md5file.close()

    for subdirectories, directories, files in os.walk("./" + name + '/html'):
        for file_name in files:
            file_loc = subdirectories + os.path.sep + file_name
            md5 = hashlib.md5(open(file_loc,'rb').read()).hexdigest()

            found = False

            for e in curmd5:
                f, h = e.strip().split(":")
                if f == file_loc:
                    if h != md5:
                        print("U => " + file_loc)
                    curmd5.remove(e)
                    found = True
                    break

            if found == False:
                print("N => " + file_loc)

    for e in curmd5:
        print("D => " + e.strip().split(":")[0])

    # for line in md5file:
    #     (file, md5) = line.strip().split(":")
    #     if os.path.isfile(file) == False:
    #         print("D => " + file)
    #     else:
    #         hash = hashlib.md5(open(file,'rb').read()).hexdigest()
    #         if hash != md5:
    #             print("U => " + file)

    # md5file.close()
    
manageParameters()