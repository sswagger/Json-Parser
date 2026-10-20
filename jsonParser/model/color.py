class Color:
	def __init__(self):
		self.neutral = "\033[0m"
		self.colors = {}

	def new_color(self, name:str, txt_red:int=-1, txt_green:int=-1, txt_blue:int=-1, bg_red:int=-1, bg_green:int=-1, bg_blue:int=-1):
		if txt_red == -1 and txt_green == -1 and txt_blue == -1:
			txt_color = ""
			txt_red = 0
			txt_green = 0
			txt_blue = 0
		else:
			txt_color = f"\033[38;2;{txt_red};{txt_green};{txt_blue}m"

		if bg_red == -1 and bg_green == -1 and bg_blue == -1:
			bg_color = ""
			bg_red = 0
			bg_green = 0
			bg_blue = 0
		else:
			bg_color = f"\033[48;2;{bg_red};{bg_green};{bg_blue}m"

		if 0 > txt_red > 255 or 0 > txt_green > 255 or 0 > txt_blue > 255:
			return
		if 0 > bg_red > 255 or 0 > bg_green > 255 or 0 > bg_blue > 255:
			return

		self.colors[name] = txt_color + bg_color

	def get_color(self, name):
		return self.colors[name]
