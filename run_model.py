import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.grid_search import GridSearchCV
from sklearn.metrics import make_scorer
from sklearn.base import TransformerMixin
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.metrics import confusion_matrix

PROFIT_CURVE = np.array([[10,-10],[0,0]])

class CustomMixin(TransformerMixin):
    def get_params(self, **kwargs):
        return dict()

    def set_params(self, **kwargs):
        for key in self.get_params():
            setattr(self, key, kwargs[key])

class FilterRows(CustomMixin):
    def fit(self, X, y):
        column_counts = X.apply(lambda x: x.count(), axis=0)
        self.keep_columns = column_counts[column_counts == column_counts.max()]
        return self

    def transform(self, X):
        return X.loc[:, self.keep_columns.index]

class ColumnFilter(CustomMixin):
    def __init__(self, cols=[]):
        # print cols
        self.cols = cols

    def get_params(self, **kwargs):
        return {'cols': self.cols}

    def fit(self, X, y):
        # Get the order of the index for y.
        return self

    def transform(self, X):
        X = X[self.cols]
        return X

class Weekdaynize(CustomMixin):
    def fit(self, X, y):
        # Get the order of the index for y.
        return self

    def transform(self, X):
        X['Weekday'] = 0
        X['Weekend'] = 0
        X['Weekend'][X['weekday_pct'] < 10] = 1
        X['Weekday'][X['weekday_pct'] > 90] = 1
        X['Weekday'] = X['Weekday'].astype(float)
        X['Weekend'] = X['Weekend'].astype(float)
        return X

class DataType(CustomMixin):
    col_types = {'str': ['city','phone']}

    def fit(self, X, y):
        return self

    def transform(self, X):
        for type, columns in self.col_types.iteritems():
            X[columns] = X[columns].astype(type)
        X.loc[:,'last_trip_date'] = pd.to_datetime(X['last_trip_date'])
        X.loc[:,'signup_date'] = pd.to_datetime(X['signup_date'])
        return X

class Dummify(CustomMixin):
    def fit(self, X, y):
        return self

    def transform(self, X):
        X = pd.get_dummies(X)
        # print X
        return X

def extract_y(df):
    return df['last_trip_date'].apply(lambda x: 1 if pd.to_datetime(x) < pd.to_datetime('2014-06-01') else 0)

def standardize_confusion_matrix(y_true, y_predict):
    cm = confusion_matrix(y_true, y_predict)
    return np.array([[cm[1,1],cm[0,1]],[cm[1,0],cm[0,0]]])

def calculate_cost_function(labels, predict_probs, threshold):
    cost_benefit = PROFIT_CURVE
    predict_probs = np.array(predict_probs[:,-1])
    predicted_labels = np.array([0] * len(predict_probs))

    predicted_labels[predict_probs >= threshold] = 1
    cm = standardize_confusion_matrix(labels, predicted_labels)
    profit = (cm * cost_benefit).sum() * 1. / len(labels)
    return profit

def fit(X_train, y_train):
    p = Pipeline([
        ('type_change', DataType()),
        ('filter', FilterRows()),
        ('weekdaynize', Weekdaynize()),
        ('columns', ColumnFilter()),
        ('dummify', Dummify()),
        ('lm', LogisticRegression(fit_intercept=True))
    ])
    X_train = X_train.reset_index()

    filter_cols = [['avg_dist','trips_in_first_30_days','city', 'phone'], \
    ['avg_dist','trips_in_first_30_days','city', 'phone', 'luxury_car_user'],\
    ['avg_dist','trips_in_first_30_days','city', 'phone','luxury_car_user','Weekday','Weekend']]
    # # GridSearch
    params = {'columns__cols': filter_cols}

    clfs = []

    threholds = [.1, .2, .3, .4, .5, .6, .7, .8, .9]
    for threshold in threholds:
        scorer = make_scorer(calculate_cost_function, greater_is_better=True, needs_proba=True, threshold=threshold)
        gscv = GridSearchCV(p, params, scoring=scorer)
        clf = gscv.fit(X_train.reset_index(), y_train)
        clfs.append(clf)

    return clfs

if __name__ == '__main__':
    X_train = pd.read_csv('data/churn_train.csv')
    y_train = extract_y(X_train)
    X_test = pd.read_csv('data/churn_test.csv')
    y_test = extract_y(X_test)

    clfs = fit(X_train, y_train)

    profits = map(lambda x: x.best_score_, clfs)

    clfs=np.array(clfs)
    scores = np.array([model.best_score_ for model in clfs])
    score_argmax = scores.argmax()
    best_clf = clfs[score_argmax]
    best_pipe =  map(lambda x: x.best_estimator_, clfs)[score_argmax]
    best_params = best_pipe.get_params(deep=True)
    best_model = best_params['lm']

    print "Train / Test Score"
    for data_set in zip([X_train, X_test],[y_train, y_test]):
        print "--"
        y_pred = best_clf.predict(data_set[0])
        print "accuracy_score: ", accuracy_score(data_set[1], y_pred)
        print "prescision_score: ", precision_score(data_set[1], y_pred)
        print "recall_score:", recall_score(data_set[1], y_pred)
        print "--"
