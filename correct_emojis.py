import os
import re
from pathlib import Path

def correct_emojis(content):
    modified = False
    
    # Pattern for whatsapp-floating and sms-floating
    # Look for any emoji after the domain/
    chat_pattern = r'(class="(?:whatsapp|sms)-floating".*?href="[^"]*/)[^-]*(-.*?")'
    if re.search(chat_pattern, content):
        content = re.sub(chat_pattern, r'\1💬\2', content)
        modified = True
    
    # Pattern for tlp-floating
    phone_pattern = r'(class="tlp-floating".*?href="[^"]*/)[^-]*(-.*?")'
    if re.search(phone_pattern, content):
        content = re.sub(phone_pattern, r'\1📞\2', content)
        modified = True
    
    return content, modified

def process_files():
    modified_files = 0
    
    for html_file in Path('.').rglob('*.html'):
        print(f"Checking file: {html_file}")
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content, was_modified = correct_emojis(content)
            
            if was_modified:
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"✓ Corrected emojis in {html_file}")
                modified_files += 1
            else:
                print(f"No corrections needed in {html_file}")
        
        except Exception as e:
            print(f"Error processing {html_file}: {str(e)}")
    
    return modified_files

if __name__ == '__main__':
    print("Starting emoji correction...")
    print("Current directory:", os.getcwd())
    print("Files found:", list(Path('.').rglob('*.html')))
    modified_count = process_files()
    print(f"\nOperation complete. Modified {modified_count} files.")
