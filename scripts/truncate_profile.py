
file_path = 'templates/profile.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

end_tag = '</html>'
split_content = content.split(end_tag)

if len(split_content) > 1:
    # Keep the first part and the tag itself
    new_content = split_content[0] + end_tag
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("File truncated successfully after </html>")
else:
    print("</html> tag not found or file already clean")
