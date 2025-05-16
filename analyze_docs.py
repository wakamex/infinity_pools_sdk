import re


def analyze_contract_details(markdown_content):
    """Analyzes CONTRACT_DETAILS.md for section details.

    Extracts contract/interface names, their protocol importance rating,
    and the character count of their description body.
    """
    sections = []
    # Split by the lookahead for a newline followed by ##.
    # Prepending a newline to content ensures the first section (if starting at line 0) is captured.
    split_pattern = r"(?=\n(?:## ))"
    raw_parts = re.split(split_pattern, "\n" + markdown_content)

    for part_text in raw_parts:
        part = part_text.strip() # remove leading/trailing whitespace from the entire chunk
        if not part or not part.startswith("## "):
            # Skip empty parts or parts not starting with a heading
            continue

        current_offset = 0 # Tracks position in `part` to determine start of section body

        # 1. Extract Title Line (must be at the beginning of the part)
        # Regex captures the '## ', the title text, and the newline or end of string.
        title_match = re.match(r"(## )(.+?)(\n|$)", part)
        if not title_match:
            continue # Should not happen due to initial check, but for safety

        full_title_str_for_display = title_match.group(2).strip()
        
        # Cleaner title extraction for display purposes
        title_for_display = full_title_str_for_display
        backtick_title_match = re.search(r"`([^`]+(?:\.sol)?)`", full_title_str_for_display)
        if backtick_title_match:
            title_for_display = backtick_title_match.group(1)
        else:
            title_for_display = full_title_str_for_display.split(" Contract")[0].split(" Library")[0].split(" Interface")[0].strip()
        
        current_offset = title_match.end() # Position after the title line (incl. its newline or EOL)

        # 2. Extract Importance Line (must immediately follow title line, after stripping leading whitespace)
        # We search in the remainder of the part string, from current_offset.
        remainder_after_title = part[current_offset:].lstrip() # lstrip to handle potential spaces before importance line
        
        importance = 0 # Default importance
        
        # Regex captures importance rating and its trailing newline or EOL.
        importance_match_in_remainder = re.match(r"\*\(Protocol Importance: (\d{1,2})/10\)\*(\n|$)", remainder_after_title)
        if importance_match_in_remainder:
            importance = int(importance_match_in_remainder.group(1))
            # Adjust current_offset: add length of stripped space + length of importance line match
            length_of_lstripped_chars = len(part[current_offset:]) - len(remainder_after_title)
            current_offset += length_of_lstripped_chars + importance_match_in_remainder.end()
        else:
            # Fallback: If importance line is not strictly after title, search for it anywhere in the part
            # This won't affect the character count of the body (which starts after title only in this case)
            # but ensures we still report an importance if it exists somewhere else in the section.
            legacy_importance_search = re.search(r"\*\(Protocol Importance: (\d{1,2})/10\)\*", part)
            if legacy_importance_search:
                importance = int(legacy_importance_search.group(1))
        
        # 3. The rest of the part is considered the section body
        section_body_text = part[current_offset:].strip()
        description_char_count = len(section_body_text)

        sections.append({
            "title": title_for_display,
            "importance": importance,
            "description_chars": description_char_count
        })
            
    return sections

def main():
    file_path = "/code/infinitypools/CONTRACT_DETAILS.md"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return
    except IOError as e: # Be more specific with file I/O errors
        print(f"Error reading file {file_path}: {e}")
        return
    except UnicodeDecodeError as e:
        print(f"Encoding error reading file {file_path}: {e}")
        return
    except OSError as e: # Catch other OS-related errors during file operations
        print(f"OS error reading file {file_path}: {e}")
        return

    analysis_results = analyze_contract_details(markdown_content)

    if not analysis_results:
        print("No sections found or parsed. Please check the markdown structure and script regex.")
        return

    print(f"{'Contract/Interface':<50} | {'Importance':<12} | {'Description Chars':<20}")
    print("-" * 90)
    for item in analysis_results:
        display_title = item['title']
        # Truncate long titles for display
        if len(display_title) > 48:
            display_title = display_title[:45] + "..."
        print(f"{display_title:<50} | {str(item['importance']) + '/10':<12} | {item['description_chars']:<20}")

if __name__ == "__main__":
    main()
