
		{{ active_list.collaborators|tojson|safe if active_list and active_list.collaborators else '[]' }}
	