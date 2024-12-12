# perceval-pontoon

Perceval backend for Pontoon.

## Backends

The backend currently managed by this package support the next repository:

* Pontoon

## Requirements

 * Python >= 3.9

You will also need some other libraries for running the tool, you can find the
whole list of dependencies in [pyproject.toml](pyproject.toml) file.

## Installation

There are several ways to install perceval-pontoon on your system: packages or source 
code using Poetry or pip.

### PyPI

perceval-pontoon can be installed using pip, a tool for installing Python packages. 
To do it, run the next command:
```
$ pip install perceval-pontoon
```

### Source code

To install from the source code you will need to clone the repository first:
```
$ git clone https://github.com/bitergia-analytics/grimoirelab-perceval-pontoon
$ cd grimoirelab-perceval-pontoon
```

Then use pip or Poetry to install the package along with its dependencies.

#### Pip
To install the package from local directory run the following command:
```
$ pip install .
```
In case you are a developer, you should install perceval-pontoon in editable mode:
```
$ pip install -e .
```

#### Poetry
We use [poetry](https://python-poetry.org/) for dependency management and 
packaging. You can install it following its [documentation](https://python-poetry.org/docs/#installation).
Once you have installed it, you can install perceval-pontoon and the dependencies in 
a project isolated environment using:
```
$ poetry install
```
To spaw a new shell within the virtual environment use:
```
$ poetry shell
```

## Example

### Pontoon

#### Translations

To download the entities and translations provided by users from a Pontoon backend
you need the URL of the server and the locales you want to obtain.

Run perceval with the Pontoon URL and the locale to fetch the entities and
translations. For example:

```
$ perceval pontoon "https://pontoon.example.com" es
```

You can also specify from what date you want to obtain the translation suggestion
with `--from-date` and `--to-date`.

#### Locales

To obtain the list of locales available in a server, run Perceval in the following way:

```
$ perceval pontoon "https://pontoon.example.com" --category locale
```

#### Users actions

To obtain the actions performed by users on a Pontoon server, you need
the server's URL, a project and the `sessionid` cookie. To get the `sessionid`
cookie, log in to the Pontoon server. Then, open the browser's developer tools
and copy the `sessionid` cookie from the cookies store or the network requests.

Run perceval with the Pontoon URL, a project and the `sessionid` cookie to fetch
the actions performed by users. It is also recommended to include a from_date
parameter. For example:

```
$ perceval pontoon "https://pontoon.example.com" --category action \
  --project amo --session-id <session_id> --from-date 2022-01-01
```

## License

Licensed under GNU General Public License (GPL), version 3 or later.
