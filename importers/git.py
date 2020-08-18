import json
import pydriller
from settings import settings
import storage
import logging


logger = logging.getLogger(__name__)


def deserialize(obj):
    return obj if isinstance(obj, storage.File) else storage.File(obj['path'])


def get_status():
    return '%d commits were loaded from %d repositories' % (settings['git/count'], len(settings['git/paths']))


def delete_all():
    pass


def poll():
    pass


def can_load_more():
    return False


def load():
    for path in settings["git/paths"]:
        load_repo(path)


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
        dict.update(self, vars(self))
        logger.info("hash: " + self.hash)

    @classmethod
    def deserialize(cls, obj):
        return GitCommit(obj)

    def render(self, query):
        return '<script>window.alert(\'%s\');</script>' % self.label


def cleanup():
    pass


def render(args):
    logger.info("render %s" % json.dumps(args, indent=4))
    return '<script>document.location=\'%s/commit/%s\';</script>' %  (args["url"], args["hash"])


settings['git/can_load_more'] = True
settings['git/can_delete'] = True
settings['git/paths'] = [
    "/Users/laffra/insights/Ikke"
]

deserialize = GitCommit.deserialize

def load_repo(path):
    repository = pydriller.GitRepository(path)
    url = repository.repo.remotes[0].config_reader.get("url")
    for commit in pydriller.RepositoryMining(path).traverse_commits():
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
                    str(modification.added),
                    str(modification.removed),
                ]
                for modification in commit.modifications
            ],
        }
        logger.info("Add %s" % json.dumps(obj, indent=4))
        storage.Storage.add_data(obj)
        settings.increment('git/count')

