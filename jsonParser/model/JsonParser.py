import re
import json
import mysql.connector
from mysql.connector import DatabaseError
from model.table import Table

#=== jsonParser class ===#
class JsonParser:
	def __init__(self, config=""):
		self.jsonObj = {}
		self.json_config = {}
		self.tables:list[Table] = []
		self.depth = 0
		self.ALLOWED_DEPTH = 10
		self.datapath = "data/data.json"
		self.db = ""
		self.port = 3306
		self.username = "root"
		self.password = "root"
		self.host = "localhost"

		# get data from file
		try:
			if config:
				with open(config, "r") as c:
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
					try:
						self.port = int(self.json_config["port"])
					except AttributeError or ValueError:
						pass
					try:
						self.username = self.json_config["user"]
					except AttributeError:
						pass
					try:
						self.password = self.json_config["pass"]
					except AttributeError:
						pass
					try:
						self.host = self.json_config["host"]
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

		# function to generate sql
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

		# function to find all data
		def recursive_fill(json_obj, parent_id, parent_table_name):
			# loop through json
			for key, value in json_obj.items():
				if type(value) is dict:
					if self.depth < self.ALLOWED_DEPTH:
						# Recurse into nested dict
						self.depth += 1
						recursive_fill(value, parent_id, parent_table_name)
					else:
						continue

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

							# check for maximum recursive depth
							if self.depth < self.ALLOWED_DEPTH:
								self.depth += 1

								# Build INSERT statement
								sql = build_insert_statement(curr_table, record, parent_id, record_id)
								sql_list.append(sql)
								# Recursively process any nested lists in this record
								recursive_fill(record, record_id, table_name)
							else:
								continue
					# Reset counter after processing this table (for top-level tables)
					if parent_table_name is None:
						table_counters[table_name] = 0
			self.depth -= 1

		if len(self.jsonObj) > 0 and len(str(self.db)) > 0:
			# Start the recursive processing
			recursive_fill(whole_json, parent_id, parent_table_name)
			self.depth = 0
			# return the sql
			return "\n".join(sql_list)
		else:
			return ""

	def create_db_schema(self, start_json=None, parent=None) -> list[Table]:
		def find_tables(start_json=None, parent=None):
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
						# check for maximum recursive depth
						if self.depth < self.ALLOWED_DEPTH:
							self.depth += 1
							# get the columns from it
							child_table.copy_columns(find_tables(whole_json.get(k)[0], child_table))
						else:
							continue

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

			self.depth -= 1
			if not new_table.json_id :
				new_table.add_column("Id", None, "INTEGER", False)

			return new_table

		if len(self.jsonObj) > 0 and len(str(self.db)) > 0:
			self.tables = []
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
			return "MAX RECURSIVE DEPTH"
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
				host=self.host,
				port=self.port,
				user=self.username,
				password=self.password,
				database=self.db
			)
			cursor = conn.cursor()

			cursor.execute(sql)
			conn.commit()
			cursor.close()
			conn.close()
		else:
			raise DatabaseError("Data Path or Database Name not specified")

	def create_db(self) -> None:
		# Connect to MySQL
		conn = mysql.connector.connect(
			host=self.host,
			port=self.port,
			user=self.username,
			password=self.password
		)
		cursor = conn.cursor()

		cursor.execute(f"CREATE DATABASE {self.db}")
		conn.commit()
		cursor.close()
		conn.close()

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
		self.json_config["port"] = self.port
		self.json_config["user"] = self.username
		self.json_config["pass"] = self.password
		self.json_config["host"] = self.host
		with open("config.json", "w") as file:
			file.write(json.dumps(self.json_config))