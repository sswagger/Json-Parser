#=== Imported Modules ===#
import cmd
import mysql.connector
from model.color import Color
from model.JsonParser import JsonParser
import shlex
import argparse

class CLI(cmd.Cmd):
	intro = (
		r"╔══════════════════════════════════════════════════╗" + "\n"
        r"║             |||   /||||   /||\   ||  ||          ║" + "\n"
		r"║              ||  ||      ||  ||  ||| ||          ║" + "\n"
		r"║              ||   \||\   ||  ||  ||||||          ║" + "\n"
		r"║          ||  ||      ||  ||__||  || |||          ║" + "\n"
		r"║           \||/   ||||/    \||/   ||  ||          ║" + "\n"
		r"║                                                  ║" + "\n"
		r"║   /||\    /||\    /||\    /||||   /||||   /||\   ║" + "\n"
		r"║  ||__||  ||__||  ||__||  ||      ||      ||__||  ║" + "\n"
		r"║  ||||/   ||||||  ||||/    \||\   ||||||  ||||/   ║" + "\n"
		r"║  ||      ||  ||  || ||       ||  ||      || ||   ║" + "\n"
		r"║  ||      ||  ||  ||  ||  ||||/    \||||  ||  ||  ║" + "\n"
		r"╠══════════════════════════════════════════════════╣" + "\n"
		r"║ Recursively parses data/data.json into MySQL DB. ║" + "\n"
		r"╚══════════════════════════════════════════════════╝" + "\n"
     )


	def __init__(self):
		super().__init__()
		self.sql = []
		self.database = JsonParser()

		self.color = Color()
		self.color.new_color("prompt", 0, 191, 0)
		self.color.new_color("error", 200, 20, 0)
		self.color.new_color("header", bg_red=0, bg_green=0, bg_blue=0)

		self.prompt = f"\n{self.color.get_color("prompt")}JSON_PARSER `{self.database.db}` :{self.color.neutral} "

	def do_help(self, arg: str):
		if "?" in arg:
			print(self.color.get_color("header") + "`help` command:" + self.color.neutral)
			print("\t`help`")
			print("\tThis command will output a table with all available commands")
			print("\tEach command will have a brief description with it")
			return
		print(r"'' = insert your string")
		print(r"[] = one element")
		print(r"|| = or")
		print(r"?? = optional")
		print()
		print(self.color.get_color("header") + r"COMMAND                             ║  DESCRIPTION                                                           " + self.color.neutral)
		print(r"help                               ║  lists all commands and their descriptions")
		print(r"set [--db-name 'name']             ║  set the databases name")
		print(r"set [--json 'path']                ║  set the datapath")
		print(r"set [--recursion-depth 'integer']  ║  set the maximum number of recursive loops")
		print(r"get                                ║  show config variables")
		print(r"read ['path']??                    ║  read data from data/data.json or specified path (must be json file)")
		print(r"sql [create || fill]               ║  generate the 'CREATE' sql or the 'INSERT' sql and save to memory")
		print(r"sql memory                         ║  show what is in the sql memory")
		print(r"sql execute                        ║  execute the sql that is in memory")
		print(r"quit                               ║  exit JSON PARSER")
		print(r"'any-command' ?                   ║  give a more complete description about the command")
		print()
		print(self.color.get_color("header") + r"JSON PARSER: created by sswagger" + self.color.neutral)

	def do_set(self, arg: str):
		if "?" in arg:
			print(self.color.get_color("header") + "`set` command:" + self.color.neutral)
			print("\t`set [--db-name 'name']?? [--json 'path']?? [--recursion-depth 'integer']??`")
			print("\tThis command will sets the config variables for future commands")
			return
		parser = argparse.ArgumentParser(prog="setdb", add_help=False)
		parser.add_argument("--db-name", required=False)
		parser.add_argument("--json", required=False)
		parser.add_argument("--recursion-depth", required=False)

		try:
			args = parser.parse_args(shlex.split(arg))
		except SystemExit:
			return

		if args.db_name:
			self.database.db = args.db_name
			self.prompt = f"\n{self.color.get_color("prompt")}JSON_PARSER `{args.db_name}` :{self.color.neutral} "
			print(f"Database name set to {args.db_name}")
		if args.json:
			self.database.datapath = args.json
			print(f"Json Path set to {args.json}")
		if args.recursion_depth:
			self.database.ALLOWED_DEPTH = int(args.recursion_depth)
			print(f"Recursive limit set to {args.recursion_depth}")

	def do_get(self, arg: str):
		if "?" in arg:
			print(self.color.get_color("header") + "`get` command:" + self.color.neutral)
			print("\t`get [json || db-name || recursion-depth || sql]??`")
			print("\tThis command will show you the current config settings")
			return

		match arg:
			case "json":
				print(f"Json Path: {self.database.datapath}")
			case "db-name":
				print(f"Database Name: {self.database.db}")
			case "recursion-depth":
				print(f"Recursion Depth Limit: {self.database.ALLOWED_DEPTH}")
			case "sql":
				print(f"In-Memory SQL: run `sql memory`")
			case _:
				print(f"Json Path: {self.database.datapath}")
				print(f"Database Name: {self.database.db}")
				print(f"Recursion Depth Limit: {self.database.ALLOWED_DEPTH}")

	def do_read(self, arg: str):
		if "?" in arg:
			print(self.color.get_color("header") + "`read` command:" + self.color.neutral)
			print("\t`read ['path']??`")
			print("\tThis command will read the data from the database")
			print("\tIf both are set then it will automatically read the data")
			return

		try:
			if arg != '':
				print("setting datapath to " + arg)
				self.database.datapath = "arg"
			print(f"reading json from {self.database.datapath}...")
			self.database.read_json()
			print(f"JSON successfully read!")

		except FileNotFoundError:
			print(f"{self.color.get_color("error")}ERROR: in command `read {arg}`{self.color.neutral}")
			print("File not found\n\tTo resolve this run `set --json 'path'`, or type `help` for docs")

	def do_sql(self, arg: str):
		if "?" in arg:
			print(self.color.get_color("header") + "`sql` command:" + self.color.neutral)
			print("\t`sql [create || fill || memory || execute]`")
			print("\t`sql create`: generate the 'CREATE TABLE' sql and save to memory")
			print("\t`sql fill`: generate the 'INSERT INTO TABLE' sql and save to memory")
			print("\t`sql memory`: read sql in memory")
			print("\t`sql execute`: run the sql that is in memory")
			return

		match arg:
			case "create":
				try:
					self.sql = []
					for i in self.database.create_db_schema():
						self.sql.append(i.create_sql())
						print(i.create_sql())

					print("sql saved in memory run `sql execute` to run memory.")
				except AttributeError:
					print(f"{self.color.get_color("error")}ERROR: in command `sql {arg}`{self.color.neutral}")
					print("No database selected\n\tTo resolve this run `set --db-name 'your-database-name'`, or type `help` for docs")

			case "fill":
				try:
					self.sql = []
					# load tables into database object
					self.database.create_db_schema()
					insert_sql = self.database.fill_db()

					insert_sql = insert_sql.split("\n")
					for i in insert_sql:
						self.sql.append(i)
						print(i)
					print("sql saved in memory run `sql execute` to run memory.")
				except AttributeError:
					print(f"{self.color.get_color("error")}ERROR: in command `sql {arg}`{self.color.neutral}")
					print("No database selected\n\tTo resolve this run `set --db-name 'your-database-name'`, or type `help` for docs")

			case "memory":
				for i in self.sql:
					print(i)

				if len(self.sql) == 0:
					print()
					print("There is no sql in memory, run `sql create` or `sql fill` to save sql to memory")

			case "execute":
				try:
					for i in self.sql:
						self.database.execute_sql(i)
					print("All sql successfully run")
				except mysql.connector.Error:
					print(f"{self.color.get_color("error")}ERROR: in command `sql {arg}`{self.color.neutral}")
					print("Database does not exist\n\tTo resolve this run `set --db-name 'your-database-name'`, or type `help` for docs")
			# todo: add `sql clear`
			# todo: add `sql execute "my query"`

	def do_quit(self, arg: str):
		if "?" in arg:
			print(self.color.get_color("header") + "`quit` command:" + self.color.neutral)
			print("\tQuit from JSON PARSER")
			print("\tAll settings will be saved, but all sql in memory will be lost")
			return False
		confirm = input("Confirm quit? [y]es/[N]o : ")

		if "y" in confirm.lower():
			self.database.save_config()
			return True
		return False

if __name__ == "__main__":
	CLI().cmdloop()
