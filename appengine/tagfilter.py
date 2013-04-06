import json
import re

class TagFilter:
  """ Filters the tags if any of the pois are in the list.
  """
  def __init__(self, file):
    with open(file) as data_file:    
      data = json.load(data_file)
      big_regexp = ""
      for exp in data["pois"]:
        exp = re.escape(exp)
        exp = exp.replace('\\ ', '\\s*')  # tags dont have spaces
        if big_regexp is "":
          big_regexp += "(" + exp
        else:
          big_regexp += "|" + exp
      big_regexp += ")"
      self.big_compiled = re.compile(big_regexp, re.IGNORECASE)

  '''
  Returns None if no match can be found.
  '''
  def match(self, str):
    if self.big_compiled:
      return self.big_compiled.search(str)
    else:
      return None

'''
Here is an example on how to use this class:
def main():
  send = TagFilter("data/newyork_pois.json")
  if send.match("Burasi 9thave mi acaba?"):
    print "supermis"

if __name__ == '__main__':
  main()
'''
