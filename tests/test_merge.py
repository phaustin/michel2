#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Suite of unit-tests for testing Michel
"""

import unittest
import textwrap
import os
import sys
import tempfile
import datetime
import locale

import michel as m
from tests import getLocaleAlias

class TestMergeConf:
    def is_needed(self, task):
        return task.todo and not task.completed

    def select_org_task(self, unmapped_task, tasklist):
        if (unmapped_task.title == "Headline A1.1") or\
           (unmapped_task.title == "Headline G") or\
           (unmapped_task.title == "Headline H"):
            return 'new'
        
        if unmapped_task.title == "Headline B2 modified":
            return m.utils.get_index(tasklist, lambda item: item.title == "Headline B2")
        if unmapped_task.title == "Headline B3":
            return m.utils.get_index(tasklist, lambda item: item.title == "Headline B3 original")

        raise Exception("Undefined behavior")

    def merge_title(self, mapping):
        if mapping.remote.title == "Headline B2 modified":
            return mapping.remote.title
        if mapping.remote.title == "Headline B3":
            return mapping.org.title

        import ipdb; ipdb.set_trace()
        raise Exception("Undefined behavior")

    def merge_completed(self, mapping):
        return mapping.org.completed or mapping.remote.completed

    def merge_closed_time(self, mapping):
        return self.__select_from([mapping.org.closed_time, mapping.remote.closed_time])

    def merge_scheduled_start_time(self, mapping):
        return self.__select_from([mapping.org.scheduled_start_time, mapping.remote.scheduled_start_time])

    def merge_scheduled_end_time(self, mapping):
        return self.__select_from([mapping.org.scheduled_end_time, mapping.remote.scheduled_end_time])

    def __select_from(self, items):        
        items = [x for x in items if x is not None]
        if len(items) == 1:
            return items[0]

        raise Exception("Undefined behavior")

    def merge_notes(self, mapping):
        if mapping.remote.notes == ['New B2 body text.']:
            return mapping.remote.notes

        raise Exception("Undefined behavior")

class TestAdapterFor3Way:
    def is_needed(self, default, task):
        return task.todo and not task.completed
    
    def select_org_task(self, default, unmapped_task, tasklist):
        if unmapped_task.title == "TitleMergeTask2":
            return m.utils.get_index(tasklist, lambda item: item.title == "TitleMergeTask2 org-edited")
        if unmapped_task.title == "TitleMergeTask3 remote-edited":
            return m.utils.get_index(tasklist, lambda item: item.title == "TitleMergeTask3")

        raise Exception("Undefined behavior")


class TestMichel(unittest.TestCase):
        
    def test_safemerge(self):
    
        org_text = textwrap.dedent("""\
            * Headline A1
            * Headline A2
            ** Headline A2.1
            * Headline B1
            ** Headline B1.1
               Remote append B1.1 body text.
            * Headline B2
            """)
        org_tree = m.TasksTree.parse_text(org_text)

        remote_tree = m.TasksTree(None)
        remote_tree.add_subtask('Headline A1').\
            add_subtask('Headline A1.1')
        remote_tree.add_subtask('Headline B1').\
            add_subtask('Headline B1.1').update(notes=["Remote append B1.1 body text."])
        remote_tree.add_subtask('Headline A2').update(todo=True).\
            add_subtask('Headline A2.1')
        remote_tree.add_subtask('Headline B2 modified').update(notes=["New B2 body text."])

        m.treemerge(org_tree, remote_tree, None, TestMergeConf())

        result_text = textwrap.dedent("""\
            * Headline A1
            ** Headline A1.1
            * Headline A2
            ** Headline A2.1
            * Headline B1
            ** Headline B1.1
               Remote append B1.1 body text.
            * Headline B2 modified
              New B2 body text.
            """)
        self.assertEqual(str(org_tree), result_text)

        
    def test_merge_sync_todo_only(self):
        org_text = textwrap.dedent("""\
            * Headline A
            * Headline B
            ** TODO Headline B1
            * TODO Headline C
            * TODO Headline D
            * Headline E
            ** DONE Headline E1
            * DONE Headline F
            ** Headline F1
            """)
        org_tree = m.TasksTree.parse_text(org_text)

        remote_tree = m.TasksTree(None)
        remote_tree.add_subtask('Headline B1').update(completed=True)
        remote_tree.add_subtask('Headline C').update(completed=True)
        remote_tree.add_subtask('Headline D').update(todo=True)
        remote_tree.add_subtask('Headline G').update(todo=True)

        m.treemerge(org_tree, remote_tree, None, TestMergeConf())
        
        result_text = textwrap.dedent("""\
            * Headline A
            * Headline B
            ** DONE Headline B1
               CLOSED: [{0}]
            * DONE Headline C
              CLOSED: [{0}]
            * TODO Headline D
            * Headline E
            ** DONE Headline E1
            * DONE Headline F
            ** Headline F1
            * TODO Headline G
            """.format(m.to_emacs_date_format(True, datetime.datetime.now())))
        self.assertEqual(str(org_tree), result_text)

        
    def test_fast_merge(self):
        org_text = textwrap.dedent("""\
            * Headline A
            * Headline B
            ** TODO Headline B1
            ** DONE Headline B2
               CLOSED: [{0}]
            ** TODO Headline B3 original
            * TODO Headline C
            * Headline D
            ** DONE Headline D1
               CLOSED: [{0}]
            * Headline E
            ** DONE Headline E1
            * TODO Headline F
            """.format(m.to_emacs_date_format(True, datetime.datetime.now())))
        org_tree = m.TasksTree.parse_text(org_text)

        remote_tree = m.TasksTree(None)
        remote_tasks = [
            remote_tree.add_subtask('Headline B1').update(completed=True),
            remote_tree.add_subtask('Headline B2 modified').update(todo=True),
            remote_tree.add_subtask('Headline B3').update(todo=True),
            remote_tree.add_subtask('Headline C').update(completed=True),
            remote_tree.add_subtask('Headline D1').update(todo=True),
            remote_tree.add_subtask('Headline G').update(todo=True),
            remote_tree.add_subtask('Headline H').update(completed=True)
        ]

        result_text = textwrap.dedent("""\
            * Headline A
            * Headline B
            ** DONE Headline B1
               CLOSED: [{0}]
            ** DONE Headline B2 modified
               CLOSED: [{0}]
            ** TODO Headline B3 original
            * DONE Headline C
              CLOSED: [{0}]
            * Headline D
            ** DONE Headline D1
               CLOSED: [{0}]
            * Headline E
            ** DONE Headline E1
            * TODO Headline F
            * TODO Headline G
            * DONE Headline H
              CLOSED: [{0}]
            """.format(m.to_emacs_date_format(True, datetime.datetime.now())))


        remote_sync_plan = m.treemerge(org_tree, remote_tree, None, TestMergeConf())

        self.assertEqual(str(org_tree), result_text)
        self.assertEqual(len(remote_sync_plan), 7)

        # Headline B1
        assertObj = next(x for x in remote_sync_plan if x['item'] == remote_tasks[0])
        self.assertEqual(assertObj['action'], 'remove')

        # Headline B2
        assertObj = next(x for x in remote_sync_plan if x['item'] == remote_tasks[1])
        self.assertEqual(assertObj['action'], 'remove')

        # Headline B3
        assertObj = next(x for x in remote_sync_plan if x['item'] == remote_tasks[2])
        self.assertEqual(assertObj['action'], 'update')
        self.assertEqual(assertObj['changes'], ['title'])
        self.assertEqual(assertObj['item'].title, 'Headline B3 original')

        # Headline C
        assertObj = next(x for x in remote_sync_plan if x['item'] == remote_tasks[3])
        self.assertEqual(assertObj['action'], 'remove')

        # Headline D1
        assertObj = next(x for x in remote_sync_plan if x['item'] == remote_tasks[4])
        self.assertEqual(assertObj['action'], 'remove')

        # Headline F
        assertObj = next(x for x in remote_sync_plan if x['item'].title == "Headline F")
        self.assertEqual(assertObj['action'], 'append')
        self.assertEqual(assertObj['item'].title, 'Headline F')

        # Headline H
        assertObj = next(x for x in remote_sync_plan if x['item'] == remote_tasks[6])
        self.assertEqual(assertObj['action'], 'remove')
        

    def test_sync_time(self):
        import michel.utils as mu
        mu.default_locale = getLocaleAlias('us')
        
        org_text = textwrap.dedent("""\
            * TODO Headline A
            * TODO Headline B
            * TODO Headline C
              SCHEDULED: <2015-12-09 Wed 20:00-21:00>
            """)
        org_tree = m.TasksTree.parse_text(org_text)

        remote_tree = m.TasksTree(None)
        remote_tree.add_subtask('Headline A').update(todo=True, scheduled_start_time=datetime.datetime(2015, 12, 9, tzinfo = m.LocalTzInfo()))
        remote_tree.add_subtask('Headline B').update(todo=True)
        remote_tree.add_subtask('Headline C').update(completed=True,
                                                     scheduled_has_time=True,
                                                     scheduled_start_time=datetime.datetime(2015, 12, 9, 20, 0, tzinfo = m.LocalTzInfo()),\
                                                     scheduled_end_time=datetime.datetime(2015, 12, 9, 21, 0, tzinfo = m.LocalTzInfo()))
        remote_tree.add_subtask('Headline D').update(todo=True, scheduled_start_time=datetime.datetime(2015, 12, 9, tzinfo = m.LocalTzInfo()))
        
        m.treemerge(org_tree, remote_tree, None, TestMergeConf())

        result_text = textwrap.dedent("""\
            * TODO Headline A
              SCHEDULED: <2015-12-09 Wed>
            * TODO Headline B
            * DONE Headline C
              CLOSED: [{0}] SCHEDULED: <2015-12-09 Wed 20:00-21:00>
            * TODO Headline D
              SCHEDULED: <2015-12-09 Wed>
            """.format(m.to_emacs_date_format(True, datetime.datetime.now())))
        self.assertEqual(str(org_tree), result_text)

    def test_3way_merge(self):
        import michel.utils as mu
        mu.default_locale = getLocaleAlias('us')
        
        base_text = textwrap.dedent("""\
            * NotTodoTestTask
            * TitleMergeTest
            ** TODO TitleMergeTask1
            ** TODO TitleMergeTask2
            ** TODO TitleMergeTask3
            * ScheduleMergeTest
            * TODO ScheduleMergeTask1
              SCHEDULED: <2015-12-09 Wed>
            * TODO ScheduleMergeTask2
              SCHEDULED: <2015-12-09 Wed>
            * TODO ScheduleMergeTask3
              SCHEDULED: <2015-12-09 Wed>
            """.format(m.to_emacs_date_format(True, datetime.datetime.now())))
        base_tree = m.TasksTree.parse_text(base_text)
        
        org_text = textwrap.dedent("""\
            * NotTodoTestTask
            * TitleMergeTest
            ** TODO TitleMergeTask1
            ** TODO TitleMergeTask2 org-edited
            ** TODO TitleMergeTask3
            * ScheduleMergeTest
            * TODO ScheduleMergeTask1
              SCHEDULED: <2015-12-09 Wed>
            * TODO ScheduleMergeTask2
              SCHEDULED: <2015-12-10 Thu>
            * TODO ScheduleMergeTask3
              SCHEDULED: <2015-12-09 Wed>
            """.format(m.to_emacs_date_format(True, datetime.datetime.now())))
        org_tree = m.TasksTree.parse_text(org_text)

        remote_tree = m.TasksTree(None)
        remote_tasks = [
            remote_tree.add_subtask('TitleMergeTask1').update(todo=True),
            remote_tree.add_subtask('TitleMergeTask2').update(todo=True),
            remote_tree.add_subtask('TitleMergeTask3 remote-edited').update(todo=True),
            remote_tree.add_subtask('ScheduleMergeTask1').update(todo=True,
                                                                 scheduled_has_time=False,
                                                                 scheduled_start_time=datetime.datetime(2015, 12, 9, tzinfo = m.LocalTzInfo())),
            remote_tree.add_subtask('ScheduleMergeTask2').update(todo=True,
                                                                 scheduled_has_time=False,
                                                                 scheduled_start_time=datetime.datetime(2015, 12, 9, tzinfo = m.LocalTzInfo())),
            remote_tree.add_subtask('ScheduleMergeTask3').update(todo=True,
                                                                 scheduled_has_time=False,
                                                                 scheduled_start_time=datetime.datetime(2015, 12, 11, tzinfo = m.LocalTzInfo())),
        ]

        result_text = textwrap.dedent("""\
            * NotTodoTestTask
            * TitleMergeTest
            ** TODO TitleMergeTask1
            ** TODO TitleMergeTask2 org-edited
            ** TODO TitleMergeTask3 remote-edited
            * ScheduleMergeTest
            * TODO ScheduleMergeTask1
              SCHEDULED: <2015-12-09 Wed>
            * TODO ScheduleMergeTask2
              SCHEDULED: <2015-12-10 Thu>
            * TODO ScheduleMergeTask3
              SCHEDULED: <2015-12-11 Fri>
            """.format(m.to_emacs_date_format(True, datetime.datetime.now())))


        remote_sync_plan = m.treemerge(org_tree, remote_tree, base_tree, m.InteractiveMergeConf(TestAdapterFor3Way()))

        self.assertEqual(str(org_tree), result_text)
        self.assertEqual(len(remote_sync_plan), 2)

        # TitleMergeTask2 org-edited
        assertObj = next(x for x in remote_sync_plan if x['item'] == remote_tasks[1])
        self.assertEqual(assertObj['action'], 'update')
        self.assertEqual(assertObj['changes'], ['title'])
        self.assertEqual(assertObj['item'].title, 'TitleMergeTask2 org-edited')

        # ScheduleMergeTask2
        assertObj = next(x for x in remote_sync_plan if x['item'] == remote_tasks[4])
        self.assertEqual(assertObj['action'], 'update')
        self.assertEqual(assertObj['changes'], ['scheduled_start_time'])
        self.assertEqual(assertObj['item'].scheduled_start_time, datetime.datetime(2015, 12, 10, tzinfo = m.LocalTzInfo()))

        
if __name__ == '__main__':
    unittest.main()
