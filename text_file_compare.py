import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import difflib
import re
from reportlab.pdfgen import canvas

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

class NumberedCanvas(canvas.Canvas):
    """Canvas that adds filenames at the top and page X of Y at the bottom."""

    def __init__(
        self,
        *args,
        left_file="",
        right_file="",
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.left_file = Path(left_file).name if left_file else ""
        self.right_file = Path(right_file).name if right_file else ""

        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)

        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_and_footer(total_pages)
            canvas.Canvas.showPage(self)

        canvas.Canvas.save(self)

    def draw_header_and_footer(self, total_pages):
        page_number = self._pageNumber
        page_width, page_height = landscape(letter)

        # Header
        self.setFont("Helvetica-Bold", 9)

        self.drawString(
            28,
            page_height - 20,
            f"Left: {self.left_file}"
        )

        self.drawRightString(
            page_width - 28,
            page_height - 20,
            f"Right: {self.right_file}"
        )

        # Footer
        self.setFont("Helvetica", 8)

        self.drawCentredString(
            page_width / 2,
            15,
            f"Page {page_number} of {total_pages}"
        )

class FileDiffViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Text File Compare v1.03")
        self.root.geometry("1500x850")
        self.root.minsize(1000, 600)

        self.file1 = None
        self.file2 = None
        self.lines1 = []
        self.lines2 = []
        self.opcodes = []

        self._build_ui()

    def _build_ui(self):
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="Open Left File", command=self.open_left).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Open Right File", command=self.open_right).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Compare Files", command=self.compare).pack(side="left", padx=12)
        ttk.Button(toolbar, text="Export Differences to PDF",
                   command=self.export_pdf).pack(side="left", padx=4)

        self.status = ttk.Label(toolbar, text="Open two text files to begin.")
        self.status.pack(side="right", padx=8)

        names = ttk.Frame(self.root, padding=(8, 0, 8, 5))
        names.pack(fill="x")

        self.left_name = ttk.Label(names, text="Left: —", anchor="w")
        self.left_name.pack(side="left", fill="x", expand=True)

        self.right_name = ttk.Label(names, text="Right: —", anchor="w")
        self.right_name.pack(side="left", fill="x", expand=True)

        # Main side-by-side area
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=8, pady=5)

        left_frame = ttk.Frame(main)
        left_frame.pack(side="left", fill="both", expand=True)

        right_frame = ttk.Frame(main)
        right_frame.pack(side="left", fill="both", expand=True)

        self.left_text = tk.Text(
            left_frame,
            wrap="none",
            font=("Consolas", 10),
            undo=False
        )
        self.right_text = tk.Text(
            right_frame,
            wrap="none",
            font=("Consolas", 10),
            undo=False
        )

        left_v = ttk.Scrollbar(left_frame, orient="vertical", command=self._scroll_y)
        right_v = ttk.Scrollbar(right_frame, orient="vertical", command=self._scroll_y)

        self.left_text.configure(yscrollcommand=left_v.set)
        self.right_text.configure(yscrollcommand=right_v.set)

        left_h = ttk.Scrollbar(left_frame, orient="horizontal", command=self.left_text.xview)
        right_h = ttk.Scrollbar(right_frame, orient="horizontal", command=self.right_text.xview)

        self.left_text.configure(xscrollcommand=left_h.set)
        self.right_text.configure(xscrollcommand=right_h.set)

        self.left_text.grid(row=0, column=0, sticky="nsew")
        left_v.grid(row=0, column=1, sticky="ns")
        left_h.grid(row=1, column=0, sticky="ew")

        self.right_text.grid(row=0, column=0, sticky="nsew")
        right_v.grid(row=0, column=1, sticky="ns")
        right_h.grid(row=1, column=0, sticky="ew")

        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)

        # Divider
        ttk.Separator(main, orient="vertical").place(relx=0.5, rely=0, relheight=1)

        # Difference tags
        for widget in (self.left_text, self.right_text):
            widget.tag_configure("added", background="#d7ffd7")
            widget.tag_configure("removed", background="#ffd6d6")
            widget.tag_configure("changed", background="#fff2b3")
            widget.tag_configure("changed_word", background="#ffbf69")
            widget.tag_configure("line_number", foreground="#777777")

        self.left_text.bind("<MouseWheel>", self._mousewheel_left)
        self.right_text.bind("<MouseWheel>", self._mousewheel_right)

    def _scroll_y(self, *args):
        self.left_text.yview(*args)
        self.right_text.yview(*args)

    def _mousewheel_left(self, event):
        delta = -1 * int(event.delta / 120)
        self.left_text.yview_scroll(delta, "units")
        self.right_text.yview_moveto(self.left_text.yview()[0])
        return "break"

    def _mousewheel_right(self, event):
        delta = -1 * int(event.delta / 120)
        self.right_text.yview_scroll(delta, "units")
        self.left_text.yview_moveto(self.right_text.yview()[0])
        return "break"

    def open_left(self):
        filename = filedialog.askopenfilename(
            title="Open Left Text File",
            filetypes=[("All files", "*.*")]
        )
        if filename:
            self.file1 = filename
            self.lines1 = self.read_text(filename)
            self.left_name.config(text=f"Left: {filename}")
            self.display_file(self.left_text, self.lines1)
            self.status.config(text="Left file loaded.")

    def open_right(self):
        filename = filedialog.askopenfilename(
            title="Open Right Text File",
            filetypes=[("All files", "*.*")]
        )
        if filename:
            self.file2 = filename
            self.lines2 = self.read_text(filename)
            self.right_name.config(text=f"Right: {filename}")
            self.display_file(self.right_text, self.lines2)
            self.status.config(text="Right file loaded.")

    @staticmethod
    def read_text(filename):
        # UTF-8 is attempted first. If the file uses another common encoding,
        # fall back to Windows-1252. Invalid bytes are replaced rather than
        # causing the program to crash.
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                with open(filename, "r", encoding=encoding) as f:
                    return f.read().splitlines()
            except UnicodeDecodeError:
                continue

        with open(filename, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()

    def display_file(self, widget, lines):
        widget.config(state="normal")
        widget.delete("1.0", "end")

        for i, line in enumerate(lines, start=1):
            widget.insert("end", f"{i:6d}  {line}\n")

        widget.config(state="disabled")

    def compare(self):
        if not self.file1 or not self.file2:
            messagebox.showwarning("Missing file", "Please open both files first.")
            return

        # SequenceMatcher gives a Git-like sequence of equal/insert/delete/replace
        # blocks. autojunk=False is important for large repetitive text files.
        self.opcodes = difflib.SequenceMatcher(
            None, self.lines1, self.lines2, autojunk=False
        ).get_opcodes()

        self._display_diff()

        added = sum(j2 - j1 for tag, i1, i2, j1, j2 in self.opcodes
                    if tag in ("insert", "replace"))
        removed = sum(i2 - i1 for tag, i1, i2, j1, j2 in self.opcodes
                      if tag in ("delete", "replace"))
        changed_blocks = sum(1 for tag, *_ in self.opcodes if tag != "equal")

        self.status.config(
            text=f"Differences: {changed_blocks} blocks | "
                 f"+{added} / -{removed} lines"
        )

    def _display_diff(self):
        self.left_text.config(state="normal")
        self.right_text.config(state="normal")

        self.left_text.delete("1.0", "end")
        self.right_text.delete("1.0", "end")

        for tag, i1, i2, j1, j2 in self.opcodes:
            if tag == "equal":
                for line_no in range(i1, i2):
                    self._insert_line(self.left_text, line_no + 1, self.lines1[line_no])
                for line_no in range(j1, j2):
                    self._insert_line(self.right_text, line_no + 1, self.lines2[line_no])

            elif tag == "delete":
                for line_no in range(i1, i2):
                    self._insert_line(
                        self.left_text, line_no + 1, self.lines1[line_no], "removed"
                    )

            elif tag == "insert":
                for line_no in range(j1, j2):
                    self._insert_line(
                        self.right_text, line_no + 1, self.lines2[line_no], "added"
                    )

            elif tag == "replace":
                left_count = i2 - i1
                right_count = j2 - j1
                count = max(left_count, right_count)

                for offset in range(count):
                    if offset < left_count:
                        lno = i1 + offset
                        left_line = self.lines1[lno]
                        self._insert_line(
                            self.left_text, lno + 1, left_line, "changed"
                        )
                    if offset < right_count:
                        rno = j1 + offset
                        right_line = self.lines2[rno]
                        self._insert_line(
                            self.right_text, rno + 1, right_line, "changed"
                        )

                # Highlight changed words for one-to-one replacements.
                if left_count == right_count:
                    for offset in range(left_count):
                        self._highlight_changed_words(
                            self.left_text,
                            self.right_text,
                            i1 + offset + 1,
                            j1 + offset + 1
                        )

        self.left_text.config(state="disabled")
        self.right_text.config(state="disabled")

    def _insert_line(self, widget, line_no, text, tag=None):
        start = widget.index("end-1c")
        widget.insert("end", f"{line_no:6d}  {text}\n")
        end = widget.index("end-1c")
        if tag:
            widget.tag_add(tag, start, end)

    def _highlight_changed_words(self, left_widget, right_widget,
                                 left_line_no, right_line_no):
        left = self.lines1[left_line_no - 1]
        right = self.lines2[right_line_no - 1]

        sm = difflib.SequenceMatcher(None, left, right, autojunk=False)

        for tag, a1, a2, b1, b2 in sm.get_opcodes():
            if tag == "equal":
                continue

            # Text starts after the six-character line number and two spaces.
            left_start = f"{left_line_no}.0 + {8 + a1} chars"
            left_end = f"{left_line_no}.0 + {8 + a2} chars"
            right_start = f"{right_line_no}.0 + {8 + b1} chars"
            right_end = f"{right_line_no}.0 + {8 + b2} chars"

            if a1 != a2:
                left_widget.tag_add("changed_word", left_start, left_end)
            if b1 != b2:
                right_widget.tag_add("changed_word", right_start, right_end)

    def export_pdf(self):
        if not self.file1 or not self.file2:
            messagebox.showwarning("Missing file", "Please open and compare two files first.")
            return

        if not REPORTLAB_AVAILABLE:
            messagebox.showerror(
                "ReportLab not installed",
                "Install ReportLab with:\n\npip install reportlab"
            )
            return

        if not self.opcodes:
            self.compare()

        default_name = (
            f"{Path(self.file1).stem}_vs_{Path(self.file2).stem}_differences.pdf"
        )

        filename = filedialog.asksaveasfilename(
            title="Save Difference Report",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf")]
        )

        if not filename:
            return

        try:
            self.create_pdf(filename)
            messagebox.showinfo("PDF created", f"Difference report saved to:\n\n{filename}")
        except Exception as exc:
            messagebox.showerror("PDF error", f"Could not create PDF:\n\n{exc}")

    def create_pdf(self, filename):
        doc = SimpleDocTemplate(
            filename,
            pagesize=landscape(letter),
            rightMargin=28,
            leftMargin=28,
            topMargin=45,
            bottomMargin=35
        )

        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        title_style.fontName = "Helvetica-Bold"
        title_style.fontSize = 16
        title_style.leading = 20

        normal = ParagraphStyle(
            "DiffNormal",
            parent=styles["Normal"],
            fontName="Courier",
            fontSize=7.5,
            leading=9
        )

        add_style = ParagraphStyle(
            "Added",
            parent=normal,
            backColor=colors.HexColor("#d7ffd7")
        )

        del_style = ParagraphStyle(
            "Removed",
            parent=normal,
            backColor=colors.HexColor("#ffd6d6")
        )

        change_style = ParagraphStyle(
            "Changed",
            parent=normal,
            backColor=colors.HexColor("#fff2b3")
        )

        story = []

        story.append(Paragraph("Text File Differences", title_style))
        story.append(Spacer(1, 8))

        #story.append(
        #    Paragraph(
        #        f"<b>Left:</b> {self._escape(Path(self.file1).name)}<br/>"
        #        f"<b>Right:</b> {self._escape(Path(self.file2).name)}",
        #        styles["Normal"]
        #    )
        #)
        #story.append(Spacer(1, 12))

        diff_rows = []

        # Only changed sections are added to the PDF.
        for tag, i1, i2, j1, j2 in self.opcodes:
            if tag == "equal":
                continue

            max_count = max(i2 - i1, j2 - j1)

            for offset in range(max_count):
                left_cell = ""
                right_cell = ""

                if offset < (i2 - i1):
                    line_no = i1 + offset + 1
                    line = self.lines1[i1 + offset]
                    left_cell = f"- {line_no}: {self._escape(line)}"

                if offset < (j2 - j1):
                    line_no = j1 + offset + 1
                    line = self.lines2[j1 + offset]
                    right_cell = f"+ {line_no}: {self._escape(line)}"

                if tag == "delete":
                    ls = del_style
                    rs = normal
                elif tag == "insert":
                    ls = normal
                    rs = add_style
                else:
                    ls = change_style if left_cell else normal
                    rs = change_style if right_cell else normal

                diff_rows.append([
                    Paragraph(left_cell or " ", ls),
                    Paragraph(right_cell or " ", rs)
                ])

        if not diff_rows:
            story.append(Paragraph("The files are identical. No differences found.", styles["Heading2"]))
        else:
            table = Table(
                diff_rows,
                colWidths=[360, 360],
                repeatRows=0,
                hAlign="LEFT"
            )
            table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(table)

        doc.build(
            story,
            canvasmaker=lambda *args, **kwargs: NumberedCanvas(
                *args,
                left_file=self.file1,
                right_file=self.file2,
                **kwargs
            )
        )

    @staticmethod
    def _escape(text):
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

def main():
    root = tk.Tk()
    app = FileDiffViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
