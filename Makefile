.PHONY: setup clean test test_unit flake8 autopep8 upload

setup:
	@pip install -Ue .\[tests\]

clean:
	find . -name "*.pyc" -exec rm '{}' ';'

unit test_unit test:
	@coverage run --branch `which nosetests` -v --with-yanc -s tests/
	@$(MAKE) coverage
	@$(MAKE) static

focus:
	@coverage run --branch `which nosetests` -vv --with-yanc --logging-level=WARNING --with-focus -i -s tests/

coverage:
	@coverage report -m --fail-under=83

coverage_html:
	@coverage html
	@open htmlcov/index.html

flake8 static:
	flake8 torstomp/
	flake8 tests/

autopep8:
	autopep8 -r -i torstomp/
	autopep8 -r -i tests/

upload:
	python ./setup.py sdist upload -r pypi
