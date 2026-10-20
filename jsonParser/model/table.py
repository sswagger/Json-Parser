class Table:
	def __init__(self):
		self.name:str = ""

		# {
		#     "key": "x",
		#     "table": Table,
		#     "type": "INTEGER",
		#     "nullable": False
		# }
		self.columns: list[dict[str, str | bool | None]] = []
		self.pk:list[str] = []
		self.json_id = False

	def create_sql(self):
		# create table sql
		sql = f"CREATE TABLE IF NOT EXISTS `{self.name}` ("

		# loop through items and write the appropriate sql
		for i in self.columns:
			sql += f"{i["key"]} {i["type"]}"

			# if key is Id, make it the primary key and auto increment
			if i["key"] == "Id":
				sql += " PRIMARY KEY AUTO_INCREMENT"
				# since this is pk, it cannot be null or link to a different table
				i["table"] = None
				i["nullable"] = False

			# if it is not nullable, add NOT NULL
			if not i["nullable"]:
				sql += " NOT NULL"

			sql += ", "

		# for composite primary keys
		if len(self.pk) > 0:
			sql += "PRIMARY KEY ("
			for j in self.pk:
				sql += j
				sql += ", "
			sql = sql[:-2]
			sql += "), "

		for j in self.columns:
			if j["table"] is not None:
				sql += f"FOREIGN KEY ({j["key"]}) REFERENCES `{j["table"].name}`(Id) ON DELETE CASCADE ON UPDATE CASCADE, "

		sql = sql[:-2]
		sql += ");"

		return sql

	def get_columns(self):
		col_names = []
		for i in self.columns:
			col_names.append(i['key'])
		return col_names

	def copy_columns(self, table):
		for i in table.columns:
			self.add_column(i["key"], i["table"], i["type"], i["nullable"])
		for i in table.pk:
			self.add_pk(i)

	def add_name(self, name):
		self.name = name

	def add_pk(self, primary_key):
		self.pk.append(primary_key)

	def add_column(self, key, table, col_type, nullable):
		if key == "Id":
			self.columns.insert(0, {"key": key, "table": table, "type": col_type, "nullable": nullable})
			return
		self.columns.append({"key": key, "table": table, "type": col_type, "nullable": nullable})
