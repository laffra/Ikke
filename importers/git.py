from classify import Label
import json
import pydriller
from settings import settings
import storage
import logging
from threadpool import ThreadPool


logger = logging.getLogger(__name__)


def deserialize(obj):
    return obj if isinstance(obj, storage.File) else storage.File(obj['path'])


def get_status():
    return '%d commits' % settings['git/count']


def delete_all():
    pass


def poll():
    load()


def can_load_more():
    return False


def load():
    settings["git/loading"] = True
    try:
        paths = settings["git/paths"]
        pool = ThreadPool(len(paths))
        for path in paths:
            pool.add_task(load_repo, path)
        pool.wait_completion()
    finally:
        settings["git/loading"] = False

COLORS = [
    "rgb(0,107,164)",
    "rgb(255,128,14)",
    "rgb(171,171,171)",
    "rgb(89,89,89)",
    "rgb(95,158,209)",
    "rgb(200,82,0)",
    "rgb(137,137,137)",
    "rgb(163,200,236)",
    "rgb(255,188,121)",
    "rgb(34,34,34)",
]

class Project(Label):
    def __init__(self, name):
        super(Project, self).__init__(name)
        self.color = COLORS[ hash(name) % len(COLORS) ]
        self.font_size = 24


class GitCommit(storage.Data):
    def __init__(self, obj):
        super(GitCommit, self).__init__(obj)
        self.uid = obj['hash']
        self.color = 'black'
        self.kind = 'git'
        self.icon = 'get?path=icons/git-icon.png'
        self.icon_size = 24
        self.font_size = 10
        self.zoomed_icon_size = 24
        self.hash = obj["hash"]
        self.url = obj["url"]
        self.message = obj["message"]
        self.label = obj["message"]
        self.author = obj["author"]
        self.committer = obj["committer"]
        self.timestamp = obj["timestamp"]
        self.project = obj["project"]
        self.changes = obj["changes"]
        words = self.message.split(' ')
        self.words = list(set(word.lower() for word in words))
        dict.update(self, vars(self))

    @classmethod
    def deserialize(cls, obj):
        return GitCommit(obj)

    def get_related_items(self):
        return super().get_related_items() + [ Project(self.project[0]) ]

    def render(self, query):
        return '<script>window.alert(\'%s\');</script>' % self.label


def cleanup():
    pass


def render(args):
    logger.info("render %s" % json.dumps(args, indent=4))
    return '<script>document.location=\'%s/commit/%s\';</script>' %  (args["url"].replace(".git", ""), args["hash"])


settings['git/can_load_more'] = True
settings['git/can_delete'] = True
settings['git/paths'] = [
    "/Users/laffra/dev/C4E",
    "/Users/laffra/dev/Ikke",
    "/Users/laffra/dev/happymeet",
    "/Users/laffra/dev/wonder",
]

deserialize = GitCommit.deserialize

def load_repo(path):
    logger.debug("#"*80)
    logger.debug(path)
    repository = pydriller.Git(path)
    url = repository.repo.remotes[0].config_reader.get("url")
    for commit in repository.get_list_commits():
        if not settings["git/loading"]:
            break
        obj = {
            "kind": "git",
            "url": url,
            "uid": "%s - %s" % (url, commit.hash),
            "hash": commit.hash,
            "label": "%s - %s - %s - %s - %s" % (url, commit.hash, commit.author.name, commit.author.email, commit.msg),
            "author": [ commit.author.name, commit.author.email],
            "committer": [ commit.committer.name, commit.committer.email],
            "timestamp": commit.committer_date.timestamp(),
            "project": [commit.project_name, commit.project_path],
            "message": "%s - %s" % (commit.project_name, commit.msg),
            "changes": [
                [
                    modification.filename,
                    modification.change_type.name,
                    str(modification.complexity),
                    str(modification.added_lines),
                    str(modification.deleted_lines),
                ]
                for modification in commit.modified_files
            ],
        }
        logger.debug("Add %s" % json.dumps(obj))
        storage.Storage.add_data(obj)

