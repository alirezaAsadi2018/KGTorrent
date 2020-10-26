"""
This module does the mapping of data from the MetaKaggle dataset to the KaggleTorrent relational database.
Use it once you have created the database schema by running the `build_db_schema` module.
"""

import os

import pandas as pd

import KaggleTorrent.config as config
from KaggleTorrent.db_connection_handler import DbConnectionHandler
from KaggleTorrent.exceptions import TableNotPreprocessedError


# PRIVATE UTILITY FUNCTIONS

def __check_table_emptiness(table_name, engine):
    """
    Checks if the database table of name `table_name` is empty.

    Args:
        table_name (str): the name of the table to be checked,
        which corresponds to the name of the .csv file from which its data is derived (omitting the extension).
        engine (Engine): the SQLAlchemy engine used to connect to the KaggleTorrent database

    Returns:
        bool: True if the database table is empty, False otherwise.

    """
    with engine.connect() as connection:
        rp = connection.execute('SELECT * FROM {} LIMIT 1'.format(table_name))
        result = rp.first()

        if result is not None:
            return False
        else:
            return True


def __read_data(meta_kaggle_path, file_name):
    """
    Reads data from the MetaKaggle .csv file given as input into a Pandas dataframe.

    Since the parsing of dates from the MetaKaggle dataset is computationally expensive,
    a serialized version of each Pandas dataframe is saved upon parsing completion.

    The goal of this function is to return a Pandas dataframe containing data from the specified dataset file.
    It checks whether such file has already been preprocessed.
    When this is the case (i.e., when the corresponding bz2 compressed pickle file is available in the dataset folder)
    it just deserializes and returns it.
    Conversely, when the file is being read for the first time, this function returns an unprocessed version
    of it as a Pandas dataframe.
    Its preprocessing (i.e., the parsing of date fields, etc.) will be handled by the function __csv_to_sql.

    Args:
        meta_kaggle_path (str): the path to the folder containing the MetaKaggle dataset on your machine
        file_name (str): the name of the specific .csv file from the MetaKaggle dataset that you want to read

    Returns:
        df (DataFrame): the Pandas dataframe containing data from the MetaKaggle file in input
        preprocessed (bool): a flag indicating whether the returned dataframe needs preprocessing or not.

    """

    full_path = os.path.join(meta_kaggle_path, file_name)
    pickle_path = os.path.join(meta_kaggle_path, '{}.bz2'.format(file_name[:-4]))

    print('Reading "{}"...'.format(file_name))
    if os.path.isfile(pickle_path):
        preprocessed = True
        df = pd.read_pickle(pickle_path)
    else:
        df = pd.read_csv(full_path)
        preprocessed = False
    return df, preprocessed


def __csv_to_sql(meta_kaggle_path, file_name, sqlalchemy_engine, date_columns=None, referenced_tables=None):
    """

    Args:
        meta_kaggle_path (str): the path to the folder containing the MetaKaggle dataset on your machine
        file_name (str): the name of the specific .csv file from the MetaKaggle dataset that you want to read
        sqlalchemy_engine (Engine): the SQLAlchemy engine connected to the KaggleTorrent database
        date_columns (list): the list of dataframe columns containing dates to be parsed
        referenced_tables (dict): the list of dataframe columns that will be assigned foreign keys in the relational database

    """

    # Check whether the database table has already been populated
    if __check_table_emptiness(table_name=file_name[:-4],
                               engine=sqlalchemy_engine):

        df, preprocessed = __read_data(meta_kaggle_path, file_name)

        # If the table is being read for the first time and needs preprocessing...
        if not preprocessed and ((len(date_columns) > 0) or referenced_tables is not None):

            print('Pre-processing "{}"...'.format(file_name))

            # Date columns parsing
            if date_columns is not None:
                print('\t- Parsing date columns...')
                df[date_columns] = df[date_columns].apply(pd.to_datetime)

            # Restricting rows so that referential integrity holds
            if referenced_tables is not None:
                print('\t- Checking the table for referential integrity...')

                for referenced_table in referenced_tables:
                    rt, prep = __read_data(meta_kaggle_path, referenced_table)

                    # The table against which we want to check the foreign key should have already been preprocessed
                    # Rise an error otherwise
                    if not prep:
                        raise TableNotPreprocessedError('Table "{}" should have already been preprocessed at this time.'
                                                        'Try importing it before "{}"'.format(referenced_table,
                                                                                              file_name))

                    # Take notes on the original table cardinality to estimate the data loss involved in the merge.
                    print('\t\tOriginal shape: {}.'.format(df.shape))

                    # For each foreign key, keep only rows that respect the constraint
                    # TODO: Check the correctness of this operation (maybe write a test here)
                    for fk in referenced_tables[referenced_table]:
                        print('\t\tJoining "{}"...'.format(referenced_table))
                        join = pd.merge(df, rt, left_on=fk, right_on='Id')
                        df = df[df[fk].isin(join['Id_y'])]
                        # Take notes on the new table cardinality to estimate the data loss involved in the merge.
                        print('\t\tNew shape: {}.'.format(df.shape))

            # Serialize the resulting dataframe object
            print('Serializing "{}"...'.format(file_name))
            pickle_path = os.path.join(meta_kaggle_path, '{}.bz2'.format(file_name[:-4]))
            df.to_pickle(pickle_path)

        # Write data to the corresponding database table
        print('Writing "{}"...'.format(file_name))
        df.to_sql(file_name[:-4], sqlalchemy_engine, if_exists='append', index=False)
        print('"{}" written to database.\n'.format(file_name))

    else:
        # TODO: maybe an exception should be raised here if the database table is found to have been already populated
        print('Table "{}" already filled.'.format(file_name[:-4]))


# POPULATION FUNCTION

def populate_db(sqlalchemy_engine, meta_kaggle_path):
    """
    Populates the KaggleTorrent database by importing data from the MetaKaggle dataset.

    Args:
        sqlalchemy_engine (Engine): the SQLAlchemy engine connected to the KaggleTorrent database
        meta_kaggle_path (str): the path to the folder containing the MetaKaggle dataset on your machine
    """

    print("DB POPULATION STARTED...\n")

    # USERS
    date_cols = ['RegisterDate']
    __csv_to_sql(meta_kaggle_path, 'Users.csv', sqlalchemy_engine,
                 date_columns=date_cols)

    # USER ACHIEVEMENTS
    date_cols = [
        'TierAchievementDate'
    ]
    ref_tables = {
        'Users.csv': [
            'UserId'
        ]
    }
    __csv_to_sql(meta_kaggle_path, 'UserAchievements.csv', sqlalchemy_engine,
                 date_columns=date_cols,
                 referenced_tables=ref_tables)

    # KERNEL LANGUAGES
    __csv_to_sql(meta_kaggle_path, 'KernelLanguages.csv', sqlalchemy_engine)

    # KERNEL VERSIONS
    date_cols = [
        'CreationDate',
        'EvaluationDate'
    ]
    ref_tables = {
        'Users.csv': [
            'AuthorUserId'
        ],
        # 'Kernels.csv': [
        #     'ScriptId'
        # ],
        'KernelLanguages.csv': [
            'ScriptLanguageId'
        ]
    }
    __csv_to_sql(meta_kaggle_path, 'KernelVersions.csv', sqlalchemy_engine,
                 date_columns=date_cols,
                 referenced_tables=ref_tables)

    # KERNELS
    date_cols = [
        'CreationDate',
        'EvaluationDate',
        'MadePublicDate',
        'MedalAwardDate'
    ]
    ref_tables = {
        'Users.csv': [
            'AuthorUserId'
        ],
        'KernelVersions.csv': [
            'CurrentKernelVersionId'
        ]
    }
    __csv_to_sql(meta_kaggle_path, 'Kernels.csv', sqlalchemy_engine,
                 date_columns=date_cols,
                 referenced_tables=ref_tables)

    # KERNEL VOTES
    date_cols = [
        'VoteDate'
    ]
    ref_tables = {
        'Users.csv': [
            'UserId'
        ],
        'KernelVersions.csv': [
            'KernelVersionId'
        ]
    }
    __csv_to_sql(meta_kaggle_path, 'KernelVotes.csv', sqlalchemy_engine,
                 date_columns=date_cols,
                 referenced_tables=ref_tables)

    # TAGS
    __csv_to_sql(meta_kaggle_path, 'Tags.csv', sqlalchemy_engine)

    # KERNEL TAGS
    ref_tables = {
        'Tags.csv': [
            'TagId'
        ],
        'Kernels.csv': [
            'KernelId'
        ]
    }
    __csv_to_sql(meta_kaggle_path, 'KernelTags.csv', sqlalchemy_engine,
                 referenced_tables=ref_tables)

    # DATASETS
    date_cols = [
        'CreationDate',
        'ReviewDate',
        'FeatureDate',
        'LastActivityDate'
    ]
    ref_tables = {
        'Users.csv': [
            'CreatorUserId'
        ],
        # 'DatasetVersions.csv': [
        #     'CurrentDatasetVersionId'
        # ]
    }
    __csv_to_sql(meta_kaggle_path, 'Datasets.csv', sqlalchemy_engine,
                 date_columns=date_cols,
                 referenced_tables=ref_tables)

    # DATASET VERSIONS.CSV
    date_cols = [
        'CreationDate'
    ]
    ref_tables = {
        'Users.csv': [
            'CreatorUserId'
        ],
        'Datasets.csv': [
            'DatasetId'
        ]
    }
    __csv_to_sql(meta_kaggle_path, 'DatasetVersions.csv', sqlalchemy_engine,
                 date_columns=date_cols,
                 referenced_tables=ref_tables)

    # DATASET TAGS
    ref_tables = {
        'Tags.csv': [
            'TagId'
        ],
        'Datasets.csv': [
            'DatasetId'
        ]
    }
    __csv_to_sql(meta_kaggle_path, 'DatasetTags.csv', sqlalchemy_engine,
                 referenced_tables=ref_tables)

    # DATASET VOTES
    date_cols = [
        'VoteDate'
    ]
    ref_tables = {
        'Users.csv': [
            'UserId'
        ],
        'DatasetVersions.csv': [
            'DatasetVersionId'
        ]
    }
    __csv_to_sql(meta_kaggle_path, 'DatasetVotes.csv', sqlalchemy_engine,
                 date_columns=date_cols,
                 referenced_tables=ref_tables)

    # KERNEL VERSION - DATASET SOURCES
    ref_tables = {
        'KernelVersions.csv': [
            'KernelVersionId'
        ],
        'DatasetVersions.csv': [
            'SourceDatasetVersionId'
        ]
    }
    __csv_to_sql(meta_kaggle_path, 'KernelVersionDatasetSources.csv', sqlalchemy_engine,
                 referenced_tables=ref_tables)

    print("DB POPULATION COMPLETED")


if __name__ == "__main__":
    # Create DB engine
    db_connection_handler = DbConnectionHandler()
    e = db_connection_handler.create_sqlalchemy_engine()

    # Populate the database
    populate_db(sqlalchemy_engine=e, meta_kaggle_path=config.meta_kaggle_path)