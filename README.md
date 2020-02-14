# Cirrolus - A P2P-Cloud

<p align="center"><img src="https://user-images.githubusercontent.com/4940804/74536932-5f5ecd00-4f39-11ea-8630-98da10f63877.png" alt="Cirrolus Logo"></p>

I programmed Cirrolus a P2P-Cloud storage prototype as part of my matriculation project (German: Maturaarbeit).
In Switzerland, each student has to do a matriculation project to complete high school.
A matriculation project is a project in an area of interest of the student which includes a written part and a presentation.

Cirrolus is a prototype for a peer-to-peer storage solution, which allows users to upload public and private files.
A file uploaded is split into, so called, fragments.
The approach used is similar to Shamir's secret sharing.
That way a node does not possess the original file.
Therefore, it can not be held accountable for potentially illegal files uploaded.
Furthermore, multiple fragments are generated and an arbitrary subsets of 4 fragments allow to reassemble the file.

Looking back on this project, I see a lot of room for improvements ;)

## Usage

Start the program:
```
./Cirrolus.py USERNAME [port]
```
The following commands exisit in the interactive prompt.
```
download FILE
getuser
join IP [PORT]
leave
list
search [FILENAME]
setuser NAME
upload FILE [p]
```

To test the program locally, copy the files into at least 5 different locations.
Start the program on different ports with different usernames.
Run `join 127.0.0.1 [Port of one node]` on each node.
You should now be able to upload files with `upload FILE` and download it again with `download FILENAME`.


## Requirements
* Python >=2.7
* PyCrypto (optional)
