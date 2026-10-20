#=== Imported Modules ===#
import json
import cmd
import mysql.connector
import re
from mysql.connector import DatabaseError
from model.table import Table
from model.color import Color
import shlex
import argparse

# TODO: Separate JSON PARSER and mcp tool into their own repos
# TODO: allow user the ability to create a database
#=== jsonParser class ===#
class JsonParser:
	def __init__(self):
		self.jsonObj = {}
		self.json_config = {}
		self.tables:list[Table] = []
		self.depth = 0
		self.ALLOWED_DEPTH = 10
		self.datapath = "data/data.json"
		self.db = ""

		# get data from file
		try:
			with open("config.json", "r") as c:
				self.json_config = json.load(c)
				try:
					self.ALLOWED_DEPTH = self.json_config["recursive_depth"]
				except AttributeError:
					pass
				try:
					self.datapath = self.json_config["data_path"]
				except AttributeError:
					pass
				try:
					self.db = self.json_config["database_name"]
				except AttributeError:
					pass
			self.read_json()
		except FileNotFoundError:
			return

	def fill_db(self, start_json=None, parent_id=None, parent_table_name=None):
		# get json string
		whole_json = start_json
		if whole_json is None:
			whole_json = self.jsonObj

		# Track record count per table for auto-increment Ids
		table_counters = {}
		# Store the generated SQL statements
		sql_list = []

		def build_insert_statement(table, record, parent_id, record_id):
			sql = f"INSERT INTO `{table.name}` ("

			# Build column list and values
			columns = []
			values = []

			for col in table.columns:
				col_name = col['key']

				# Skip Id column if auto-increment
				if col_name == "Id" and not table.json_id:
					continue

				columns.append(col_name)

				# Determine the value
				value = None
				if col_name == "Id":
					# Use the computed record_id
					value = record_id
				if col['table'] is not None:
					# This is a foreign key to parent - use parent_id
					value = parent_id
				if col_name in record:
					value = record[col_name]

				# Format the value based on type
				if value is None:
					values.append("NULL")
				elif col['type'] == "VARCHAR(50)":
					# Escape single quotes in string values
					escaped = str(value).replace("'", "''")
					values.append(f"'{escaped}'")
				elif col['type'] == "BOOLEAN":
					values.append("1" if value else "0")
				elif col['type'] == "DATETIME":
					# Keep datetime as-is (ISO format from JSON)
					values.append(f"'{value}'")
				else:
					# INTEGER, DECIMAL, etc.
					values.append(str(value))

			sql += ", ".join(columns) + ") VALUES ("
			sql += ", ".join(values) + ");"

			return sql
		def recursive_fill(json_obj, parent_id, parent_table_name):
			# check for maximum recursive depth
			self.depth += 1
			if self.depth > self.ALLOWED_DEPTH:
				self.depth = 0
				return

			# loop through json
			for key, value in json_obj.items():
				if type(value) is dict:
					# Recurse into nested dict
					recursive_fill(value, parent_id, parent_table_name)
				elif type(value) is list:
					# This is a table
					table_name = key

					# find the correct table
					curr_table = None
					for t in self.tables:
						if t.name == table_name:
							curr_table = t
							break
					# skip if no matching table
					if curr_table is None:
						continue

					# Initialize counter for this table if needed
					if table_name not in table_counters:
						table_counters[table_name] = 0

					# Process each record in the list
					for record in value:
						if record is not None:
							# Determine the Id value for this record
							if curr_table.json_id:
								# Use the Id from the JSON
								record_id = record.get("Id")
								# Update counter if record_id is higher
								if record_id and record_id > table_counters[table_name]:
									table_counters[table_name] = record_id
							else:
								# Auto-increment
								table_counters[table_name] += 1
								record_id = table_counters[table_name]

							# Build INSERT statement
							sql = build_insert_statement(curr_table, record, parent_id, record_id)
							sql_list.append(sql)

							# Recursively process any nested lists in this record
							recursive_fill(record, record_id, table_name)

					# Reset counter after processing this table (for top-level tables)
					if parent_table_name is None:
						table_counters[table_name] = 0

		if len(self.jsonObj) > 0 and len(str(self.db)) > 0:
			# Start the recursive processing
			recursive_fill(whole_json, parent_id, parent_table_name)
			self.depth = 0
			# return sql
			return "\n".join(sql_list)
		else:
			return ""

	def create_db_schema(self, start_json=None, parent=None) -> list:
		def find_tables(start_json=None, parent=None):
			# check for maximum recursive depth
			self.depth += 1
			if self.depth > self.ALLOWED_DEPTH:
				self.depth = 0
				return Table()
			# get data
			whole_json = start_json
			if whole_json is None:
				whole_json = self.jsonObj

			# create a new table
			new_table = Table()
			# loop through json
			for k, v in whole_json.items():
				# look for an id already defined
				if "Id" in k:
					new_table.json_id = True
				curr_table_i = len(self.tables)

				# check the type of the value
				if type(v) is list:
					if type(v[0]) is dict:
						# if it's a list of dictionaries, then it is a child table

						# create a new table, and add the name
						child_table = Table()
						child_table.add_name(k)
						# get the columns from it
						child_table.copy_columns(find_tables(whole_json.get(k)[0], child_table))

						# add current table's name as parent
						if parent is not None:
							if len(child_table.pk) > 0:
								child_table.add_column(parent.name+"_Id", parent, "INTEGER", True)
								child_table.add_pk(parent.name+"_Id")
							else:
								child_table.add_column(parent.name+"_Id", parent, "INTEGER", False)

							# add it to the list of tables
						self.tables.insert(curr_table_i, child_table)

				elif type(v) is str:
					# if it is a string, then it is either a datetime or a varchar
					pat = "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
					if re.search(pat, v):
						new_table.add_column(k, None, "DATETIME", True)
					else:
						new_table.add_column(k, None, "VARCHAR(50)", True)
				elif type(v) is int:
					# if it's an int, then check if it's an id
					if "_Id" in k:
						# check that the table exists, and it's not just a naming coincident
						for j in self.tables:
							if j.name == k[:-3]:
								new_table.add_column(k, j, "INTEGER", True)
								new_table.add_pk(str(k))
								new_table.json_id = True
					else:
						new_table.add_column(k, None, "INTEGER", True)
				elif type(v) is bool:
					# boolean
					new_table.add_column(k, None, "BOOLEAN", True)
				elif type(v) is float:
					# decimal
					new_table.add_column(k, None, "DECIMAL(5, 2)", True)

			if not new_table.json_id :
				new_table.add_column("Id", None, "INTEGER", False)

			return new_table

		if len(self.jsonObj) > 0 and len(str(self.db)) > 0:
			# call recursive loop
			find_tables(start_json, parent)
			# reset depth and return tables
			self.depth = 0
			return self.tables
		else:
			return []

	def get_json(self, keys:list, i:int=0, start_json=None) -> str:
		# check for maximum recursive depth
		self.depth += 1
		if self.depth > self.ALLOWED_DEPTH:
			self.depth = 0
			return ""
		# get or set json object
		json_obj = start_json
		if json_obj is None:
			json_obj = self.jsonObj

		if i + 1 < len(keys):
			# if we haven't reached the end of keys, get the value and continue
			return self.get_json(keys, i=i+1, start_json=json_obj[keys[i]])
		else:
			# since this is the last key, just return the value
			self.depth = 0
			return json_obj[keys[i]]

	def get_table(self, table_name:str) -> str:
		for table_i in self.tables:
			if table_i.name == table_name:
				return table_i.create_sql()

		return "NOT FOUND"

	def execute_sql(self, sql:str) -> None:
		if len(self.jsonObj) > 0 and len(str(self.db)) > 0:
			# Connect to MySQL
			conn = mysql.connector.connect(
				host="localhost",
				port=3306,
				user="root",
				password="root",
				database=self.db
			)
			cursor = conn.cursor()

			cursor.execute(sql)
			conn.commit()
			cursor.close()
			conn.close()
		else:
			raise DatabaseError("Data Path or Database Name not specified")

	def read_json(self) -> None:
		with open(self.datapath, "r") as file:
			whole_json = json.load(file)
			self.jsonObj = whole_json

	def set_db_name(self, name:str) -> None:
		self.db = name

	def set_data_path(self, path:str) -> None:
		self.datapath = path

	def set_max_recursion(self, max:int) -> None:
		self.ALLOWED_DEPTH = max

	def save_config(self) -> None:
		self.json_config["recursive_depth"] = self.ALLOWED_DEPTH
		self.json_config["data_path"] = self.datapath
		self.json_config["database_name"] = self.db
		with open("config.json", "w") as file:
			file.write(json.dumps(self.json_config))

class CLI(cmd.Cmd):
	intro = (
		r"╔==================================================╗" + "\n"
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
		r"╠==================================================╣" + "\n"
		r"║ Recursively parses data/data.json into MySQL DB. ║" + "\n"
		r"╚==================================================╝" + "\n"
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
		# todo: update help
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
		print(r"read [json || 'path']              ║  read data from data/data.json or specified path (must be json file)")
		print(r"sql [create || fill]               ║  generate the 'create table' sql or the 'insert' sql and save to memory")
		print(r"sql memory                         ║  show what is in the sql memory")
		print(r"sql execute                        ║  execute the sql that is in memory")
		print(r"quit                               ║  exit JSON PARSER")
		print(r"'your command' ?                   ║  give a more complete description about the command")
		print()
		print(self.color.get_color("header") + r"JSON PARSER: created by sswagger" + self.color.neutral)

	def do_set(self, arg: str):
		if "?" in arg:
			print(self.color.get_color("header") + "`set` command:" + self.color.neutral)
			print("\t`set [--db-name 'name']?? [--json 'path']?? [--recursion-depth 'integer']??`")
			print("\tThis command will set the databases name or datapath for future commands")
			print("\tIf both are set then it will automatically read the data")
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
		# todo: add help
		match arg:
			case "json":
				print(f"Json Path: {self.database.datapath}")
			case "dbname":
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
			# todo: update help
			print(self.color.get_color("header") + "`read` command:" + self.color.neutral)
			print("\t`read [json || 'path']`")
			print("\tThis command will read the data from the database")
			print("\tIf both are set then it will automatically read the data")
			return

		try:
			print(f"reading json from {self.database.datapath}...")
			self.database.read_json()
			print(f"JSON successfully read!")
		except FileNotFoundError:
			print(f"{self.color.get_color("error")}ERROR: in command `read {arg}`{self.color.neutral}")
			print("File not found\n\tTo resolve this run `set --json 'path'`, or type `help` for docs")

	def do_sql(self, arg: str):
		if "?" in arg:
			# todo: update help
			print(self.color.get_color("header") + "`sql` command:" + self.color.neutral)
			print("\t`sql [create || fill || memory || execute]`")
			print("\t`sql create`: generate the 'create table' sql and save to memory")
			print("\t`sql fill`: generate the 'fill table' sql and save to memory")
			print("\t`sql memory`: read sql in memory")
			print("\t`sql execute`: run the sql that is in memory")
			return

		match arg:
			case "create":
				try:
					self.sql = []
					self.database.create_db_schema()
					for i in self.database.tables:
						self.sql.append(i.create_sql())
						print(i.create_sql())

					print("sql saved in memory run `sql execute` to run memory.")
				except AttributeError:
					print(f"{self.color.get_color("error")}ERROR: in command `sql {arg}`{self.color.neutral}")
					print("No database selected\n\tTo resolve this run `set --db-name 'your-database-name'`, or type `help` for docs")

			case "fill":
				try:
					self.sql = []
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
				except AttributeError:
					print(f"{self.color.get_color("error")}ERROR: in command `sql {arg}`{self.color.neutral}")
					print("No database selected\n\tTo resolve this run `set --db-name 'your-database-name'`, or type `help` for docs")
				except mysql.connector.Error:
					print(f"{self.color.get_color("error")}ERROR: in command `sql {arg}`{self.color.neutral}")
					print("Database does not exist\n\tTo resolve this run `set --db-name 'your-database-name'`, or type `help` for docs")
			# todo: add `sql clear`

	def do_quit(self, arg: str):
		if "?" in arg:
			print(self.color.get_color("header") + "`quit` command:" + self.color.neutral)
			print("\tQuit from JSON PARSER")
			print("\tAll sql in memory will be lost")
			return False
		confirm = input("Confirm quit? [y]es/[N]o : ")

		if "y" in confirm.lower():
			self.database.save_config()
			return True
		return False

if __name__ == "__main__":
	CLI().cmdloop()
