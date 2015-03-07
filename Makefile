clean:
	find . -name "*.pyc" -exec rm '{}' ';'

test: test_unit flake8

test_unit:
	python setup.py test

flake8:
	flake8 torstomp/
	flake8 tests/

autopep8:
	autopep8 -r -i torstomp/
	autopep8 -r -i tests/

upload:
	python ./setup.py sdist upload -r pypi
