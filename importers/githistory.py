import pydriller

def load_repo(path):
    for commit in pydriller.RepositoryMining(path).traverse_commits():
        print(
            'Mod {}<{}> at {}'.format(
                commit.author.name,
                commit.author.email,
                commit.committer_date
            )
    )

if __name__ == '__main__':
    load_repo("/Users/laffra/insights/Ikke")

