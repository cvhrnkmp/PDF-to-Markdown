import glob
import os
import sys
from langchain.docstore.document import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter
import json
from typing import List
from uuid import uuid4
import fitz
import re


def get_pdf_paths(folder_path: str) -> List:
    """
    Return pdf-files's path

    Args:
        folder_path (str): folder path of pdf-files

    Returns:
        List: list with path of pdf-files
    """
    return glob.glob(f"{folder_path}/*.pdf", recursive=True)


def collect_unicode_sequences(strings: str) -> List:
    """
    Collects all Unicode escape sequences from a list of strings.

    Args:
        strings (list of str): List of input strings to search for Unicode escape sequences.

    Returns:
        list: A list of all found Unicode escape sequences across the input strings.
    """
    # Regular expression to match Unicode escape sequences
    pattern = r"\\u[0-9a-fA-F]{4}"

    all_matches = []

    for text in strings:
        # Encode the text to escape sequences and decode back to a string
        escaped_text = text.encode("unicode_escape").decode("utf-8")
        # Find all matches in the current text
        matches = re.findall(pattern, escaped_text)
        # Add matches to the result list
        all_matches.extend(matches)

    return all_matches


class MarkdownParsingUtils:

    def __init__(self):
        # Key-Value for replacements
        self.replacements = {
            "\\u010d": "č",
            "\\u03b1": "α",
            "\\u03b2": "β",
            "\\u03b3": "γ",
            "\\u03b5": "ε",
            "\\u03bc": "μ",
            "\\u0d57": "ൗ",
            "\\u2013": "–",
            "\\u2019": "’",
            "\\u201c": '"',
            "\\u201d": '"',
            "\\u201e": '"',
            "\\u2022": "•",
            "\\u2026": "...",
            "\\u21d2": "⇒",
            "\\u2211": "∑",
            "\\u2212": "−",
            "\\u2219": "∙",
            "\\u2264": "≤",
            "\\u2265": "≥",
            "\\u22c5": "⋅",
            "\\uf020": " ",  # Replace with a space
            "\\uf072": " ",  # Replace with a space
            "\\uf0a7": "-",  # Decorative bullet
            "\\uf0a9": "→",  # Decorative arrow
            "\\uf0aa": "⇒",  # Decorative double arrow
            "\\uf0f0": "✔",  # Decorative checkmark
        }

    def analyze_fonts_per_block(self, pdf_path: str) -> List:
        """
        Analyzes fonts used in each block on each page of the PDF and assign each block a class - is it a header or text?

        Args:
            pdf_path (str): Path to the PDF file.

        Returns:
            List: A list of dictionary of page data, with blocks and their class - header or text.
        """
        try:
            pdf_document = fitz.open(pdf_path)
            pages_data = {}

            for page_number in range(len(pdf_document)):
                page = pdf_document[page_number]

                blocks = page.get_text("dict")["blocks"]
                blocks_data = []

                for block in blocks:
                    if "lines" in block:  # Process text blocks only
                        block_info = []
                        text_class = None
                        for line in block["lines"]:

                            for span in line["spans"]:
                                # Each span has text, font, size, etc.
                                if (
                                    len(span["text"].strip()) < 1
                                ):  # continue if textbox is emtpy
                                    continue

                                # Filter textboxes of header, footer and the right margin
                                if not (
                                    span["bbox"][3] > 65
                                    and span["bbox"][1] < 750
                                    and span["bbox"][2] < 575
                                ):
                                    continue

                                font_name = span.get("font", "Unknown")
                                font_size = span.get("size", "Unknown")
                                text = span.get("text", "")

                                # Classify textbox based on fontname and -size
                                if font_name == "Arial,Bold":
                                    if font_size > 12.5:
                                        text_class = "h1"

                                    if (
                                        font_size > 11
                                        and font_size <= 12.5
                                        and text.count(".") == 1
                                    ):
                                        text_class = "h2"

                                    if (
                                        font_size > 11
                                        and font_size < 12
                                        and text.count(".") == 2
                                    ):
                                        text_class = "h3"

                                    if (
                                        font_size > 11
                                        and font_size < 12
                                        and text.count(".") == 3
                                    ):
                                        text_class = "h4"

                                    if (
                                        font_size > 11
                                        and font_size < 12
                                        and text.count(".") == 4
                                    ):
                                        text_class = "h5"

                                    if text_class != None:
                                        text_class = text_class

                                elif font_name == "Arial-BoldMT":
                                    if font_size > 13 and text.count(".") == 0:
                                        text_class = "h1"
                                    if (
                                        font_size >= 10.9
                                        and font_size < 13
                                        and text.count(".") == 1
                                    ):  # > 12 < 13
                                        text_class = "h2"
                                    if (
                                        font_size < 11
                                        and font_size > 10
                                        and text.count(".") == 2
                                    ):  # < 11
                                        text_class = "h3"
                                    if (
                                        font_size < 11
                                        and font_size > 10
                                        and text.count(".") == 3
                                    ):  # < 11
                                        text_class = "h4"
                                    if (
                                        font_size < 11
                                        and font_size > 10
                                        and text.count(".") == 4
                                    ):  # < 11
                                        text_class = "h5"
                                    if text_class != None:
                                        text_class = text_class

                                # Collect block information
                                block_info.append(
                                    {
                                        "text": text,
                                        "text_class": (
                                            text_class if text_class != None else "Text"
                                        ),
                                        "font_name": font_name,
                                        "font_size": font_size,
                                        "color": span.get("color", "Unknown"),
                                    }
                                )

                        # Add block to page information
                        blocks_data.append(block_info)

                pages_data[page_number + 1] = blocks_data  # Store per-page data

            pdf_document.close()
            return pages_data
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def convert_to_markdown(self, document)->List:
        """
        Convert page information in markdown-file based on text classes of text blocks

        Args:
            document (dict): text blocks

        Returns:
            List[str]: markdown string
        """
        markdown_str = []
        for page, blocks in document.items():
            if page < 4:  # Jump over the first n-pages
                continue
            for block in blocks:
                if len(block) < 1:
                    continue

                text_class = block[0]["text_class"]
                prefix = ""

                # Convert text_class in markdown
                if text_class == "h1":
                    prefix = "# "
                if text_class == "h2":
                    prefix = "## "
                if text_class == "h3":
                    prefix = "### "
                if text_class == "h4":
                    prefix = "#### "
                if text_class == "h5":
                    prefix = "##### "

                # Replace unicode-errors
                block_text = [
                    self.replace_unicode_sequences(span["text"], self.replacements)
                    for span in block
                ]
                # Create markdown string
                markdown_str.append(
                    prefix + " ".join(block_text).replace("\uf0b7", "-")
                )

        return markdown_str

    def replace_unicode_sequences(self, text:str, replacements:dict) -> str:
        """
        Replaces Unicode escape sequences in a string with specified replacements.

        Args:
            text (str): Input text containing Unicode escape sequences.
            replacements (dict): Dictionary mapping Unicode escape sequences to replacement values.

        Returns:
            str: The text with Unicode sequences replaced.
        """
        # Encode the text to escape sequences and decode back to a string
        escaped_text = text.encode("unicode_escape").decode("utf-8")

        # Replace each Unicode escape sequence based on the replacements dictionary
        for unicode_escape, replacement in replacements.items():
            escaped_text = escaped_text.replace(unicode_escape, replacement)

        # Decode the final text back to Unicode
        return escaped_text.encode("utf-8").decode("unicode_escape")

    def parse_markdown_files(self, folder_path="..\PDF-Files"):
        """
        Parse PDF-files to markdown and write back to path

        Args:
            folder_path (str, optional): Path to PDF-files. Defaults to "..\PDF-Files".
        """
        pdf_paths = get_pdf_paths(folder_path)
        unicode_list = []
        for path in pdf_paths:
            # print(path)

            document_in = self.analyze_fonts_per_block(path)
            document_md = self.convert_to_markdown(document_in)
            unicode_list.extend(collect_unicode_sequences("\n".join(document_md)))
            with open(path[:-4] + ".md", "w", encoding="utf-8") as file:
                # (path[:-4]+ ".md")
                file.write("\n".join(document_md))
                print("Done")


class MarkdownSplitter:

    def __init__(self):
        self.split_on_headers = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
            ("####", "Header 4"),
            ("#####", "Header 5"),
        ]
        self.markdown_splitter = MarkdownHeaderTextSplitter(self.split_on_headers)

    def load_data(self, path="../PDF-Files") -> List:
        """Load markdown files

        Args:
            path (str, optional): Path to markdown-files. Defaults to "../PDF-Files".

        Returns:
            str: Markdown files as string.
        """
        # Define the path where to search for markdown files
        print(os.path.join(path, "*.md"))
        # Use glob to find all markdown files (*.md)
        markdown_files = glob.glob(os.path.join(path, "*.md"))

        # List to store the content of each file
        markdown_contents = []

        # Read and store the content of each markdown file
        for file in markdown_files:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

                markdown_contents.append((content, file))

        return markdown_contents

    def load_metadata(self, path:str) -> str:
        """Load metadata of the documents

        Args:
            path (str): Path to metadata.json

        Returns:
            str: JSON-string with metadata of pdf-files
        """
        path = "../PDF-Files/meta.json"
        with open(path, "r") as file:
            return json.load(file)

    def split_markdown(self, documents:Document) -> List[Document]:
        """Split markdowns in text chunks

        Args:
            documents (Document): PDF-files as langchain document

        Returns:
            document: List of text chunks as langchain document
        """
        return_docs = []
        for content, source in documents:
            docs = self.markdown_splitter.split_text(content)

            uuid = uuid4()
            previous_uuid = None
            for docu in docs:
                docu.metadata["source"] = source.split("/")[-1]
                docu.metadata["uuid"] = str(uuid)
                if previous_uuid:
                    docu.metadata["previous"] = previous_uuid
                previous_uuid = uuid
            return_docs.append(docs)
        return return_docs
