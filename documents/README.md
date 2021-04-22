# How to write my part with help of this template?

1. Do not change any file out of your directory except:
    - you need further packages: import them in "config/includes.tex"
    - you want more self-written command: define them in "config/defs.tex"
    - you have to add a citation source: add it in "biblio.bib"
    - you want to add more figures, graphs, etc.: add them in "figures"

2. If you are working with multiple persons i.e. on the checkpoint part you don't have to write in the same file. You can write your part in a separate file (e.g. "checkpoint_creation.tex") and directly start with the content. You don't have to do any LaTeX related import, headers, etc. by yourself. If you want to include your part to the rest of the paper just go to the ".tex" file which has the same name as your directory and enter the path to your file starting with the most high-level folder ( e.g. "\input{modules/checkpoint/checkpoint_creation.tex}") in it. To compile the LaTeX file and further, test if everything works fine you have to compile "rotrans_final_paper.tex" to generate the resulting ".pdf" . 

3. If you are unsure how your file should look like you can find an example in "modules/abccore/example.tex"