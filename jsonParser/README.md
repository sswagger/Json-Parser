# JSON PARSER

## Description
Takes a JSON object and parse it into a database.
* Language
  * English
  * Programming
    * Python
* Type of Application
  * CLI
* Author
  * Sam Swagger
  * Limited help from Qwen Coder

## How to run
Install [anaconda](https://www.anaconda.com/download) or [mini-conda](https://www.anaconda.com/download) (further reading [here](https://www.anaconda.com/docs/getting-started/concepts/anaconda-or-miniconda)).
Then run the following at the project root in a conda terminal session:
```bash
conda env create -f ./jsonParser/jsonParserConda.yml
```
This will install all the necessary packages and create a python environment for JSON PARSER.
Ensure you activate the correct environment.
You can do that with the following code:
```bash
conda activate restaurant-stats
```
The terminal prompt line should look similar to this `(restaurant-stats) your/current/path> `.
Then run the following to start JSON PARSER:
```bash
python ./jsonParser/JsonParser.py
```

## Notes
For using your own JSON object, there are some restrictions on how the JSON can be formatted:
1.  Every list of objects in interpreted as a new table.  
	eg:
```json
{
  "my_table": [
    {},
    {}
  ]
}
```
2.  Within the table, every object is interpreted as a row of `column_name: datapoint`.
	This means that every object must have the same attributes (but different values).
	The parser will take the attributes of the first row and use it as the table's schema.  
```json
{
  "my_table": [
    {"f_name": "Sam", "l_name": "Swagger"},
    {"f_name": "Red", "l_name": "Leader"}
  ]
}
```
3.  Children tables are nested "tables".
	In the example below, `github` will be automatically given an FK called `my_table_Id`
```json
{
  "my_table": [
    {
      "f_name": "Sam",
      "l_name": "Swagger",
      "github": [
        {
          "link": "https://github.com/sswagger/ChatAgent",
          "desc": "an ai chat agent"
        }
      ]
    },
    {
      "f_name": "Red",
      "l_name": "Leader",
      "github": [
        {
          "link": "https://github.com/sswagger/Artificial-Tech",
          "desc": "website for a made-up company"
        },
        {
          "link": "https://github.com/sswagger/Medieval-Manager",
          "desc": "javafx project for CRUD operations"
        }
      ]
    }
  ]
}
```
4.  For M:N relationships, include a key that ends in "_Id"; and define that table elsewhere.
	Any column named "Id" is interpreted as the `PK`.
	For example, the table `fav_movie` will have two `FK's` (`my_table_Id` and `movie_Id`) and both will be a `PK`.
```json
{
  "movie": [
    {"Id": 1, "name": "Star Wars"},
    {"Id": 2, "name": "Lord of the Rings"}
  ],
  "my_table": [
    {
      "f_name": "Sam",
      "l_name": "Swagger",
      "fav_movie": [
        {
          "movie_Id": 1
        },
        {
          "movie_Id": 2
        }
      ]
    },
    {
      "f_name": "Red",
      "l_name": "Leader",
      "fav_movie": [
        {
          "movie_Id": 1
        }
      ]
    }
  ]
}
```