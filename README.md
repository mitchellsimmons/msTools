# msTools

A set of libraries and tools, primarily for interfacing with Autodesk Maya and related APIs.

**_NOTE:_**  This repository is no longer actively maintained.

## _Documentation_

Complete documentation found [here](https://mitchellsimmons.github.io/msTools/).

## _Distribution_

#### Method 1

Download or clone this repository to a directory on your computer.

Create or locate a text file named `Maya.env`, usually in the following directory:

* **Windows**:<br/>
`<drive>:\Users\<username>\Documents\maya\<version>`

* **Mac OS X**:<br/>
`~/Library/Preferences/Autodesk/maya/<version>`

* **Linux**:<br/>
`~/maya/<version>`

Configure the `MAYA_MODULE_PATH` variable within `Maya.env`, using a semicolon `;` on Windows or a colon `:` on Linux and Mac OS X to separate existing paths:

* **Windows**:<br/>
`MAYA_MODULE_PATH = <absolute path to>\msTools\module`

* **Linux / Mac OS X**:<br/>
`MAYA_MODULE_PATH = <absolute path to>/msTools/module`

#### Method 2

Download or clone this repository to a directory on your computer.

Move the `msTools.mod` file from the `\msTools\module` directory to an existing directory in the `MAYA_MODULE_PATH`, for example:

* **Windows**:<br/>
`<drive>:\Users\<username>\Documents\maya\<version>\modules`

* **Mac OS X**:<br/>
`~/Library/Preferences/Autodesk/maya/<version>/modules`

* **Linux**:<br/>
`~/maya/<version>/modules`

Open the `msTools.mod` file and change the relative path of the module directory to an absolute path, so that this line:

`+ msTools 1.0 ./`

Now looks like this line:

`+ msTools 1.0 <absolute path to>/msTools/module/`
