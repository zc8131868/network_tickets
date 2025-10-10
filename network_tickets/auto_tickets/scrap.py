import re
pattern = r'[ ,\n、]'
a = ['1', '', '2  3 4   5 ']

new_a = [item.replace(' ', '') for item in a if item.strip()]

print(new_a)