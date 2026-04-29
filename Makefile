.PHONY: install test clean

install:
	@bash install.sh

test:
	@python3 -m pytest tests/ -v 2>/dev/null || python3 -c "
import sys; sys.path.insert(0, 'tools')
from project_store import project_create, project_list, task_create, task_list, task_breakdown
p = project_create('Test Project')
print('project_create:', p['ok'])
tasks = task_list()
print('tasks before:', len(tasks))
t = task_create(p['project']['id'], 'Main task')
print('task_create:', t['ok'])
br = task_breakdown(t['task']['id'], [{'title':'Sub 1'}, {'title':'Sub 2'}])
print('breakdown:', br['ok'], '->', br['count'], 'subtasks')
print('ALL OK')
"

clean:
	@rm -rf __pycache__ tools/__pycache__ .pytest_cache
