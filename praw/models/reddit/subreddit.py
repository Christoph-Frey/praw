"""Provide the Subreddit class."""
from ...const import API_PATH
from ..util import BoundedSet
from ..listing.generator import ListingGenerator
from ..listing.mixins import SubredditListingMixin
from .base import RedditBase
from .mixins import MessageableMixin


class Subreddit(RedditBase, MessageableMixin, SubredditListingMixin):
    """A class for Subreddits."""

    EQ_FIELD = 'display_name'
    MESSAGE_PREFIX = '#'

    def __init__(self, reddit, display_name=None, _data=None):
        """Initialize a Subreddit instance.

        :param reddit: An instance of :class:`~.Reddit`.
        :param display_name: The name of the subreddit.

        """
        if bool(display_name) == bool(_data):
            raise TypeError(
                'Either `display_name` or `_data` must be provided.')
        super(Subreddit, self).__init__(reddit, _data)
        if display_name:
            self.display_name = display_name
        self._path = API_PATH['subreddit'].format(subreddit=self.display_name)
        self._prepare_relationships()
        self.flair = SubredditFlair(self)
        self.mod = SubredditModeration(self)
        self.stream = SubredditStream(self)

    def _info_path(self):
        return API_PATH['subreddit_about'].format(subreddit=self.display_name)

    def _prepare_relationships(self):
        for relationship in ['banned', 'contributor', 'moderator', 'muted',
                             'wikibanned', 'wikicontributor']:
            setattr(self, relationship,
                    SubredditRelationship(self, relationship))

    def submit(self, title, selftext=None, url=None, resubmit=True,
               send_replies=True):
        """Add a submission to the subreddit.

        :param title: The title of the submission.
        :param selftext: The markdown formatted content for a ``text``
            submission.
        :param url: The URL for a ``link`` submission.
        :param resubmit: When False, an error will occur if the URL has already
            been submitted (Default: True).
        :param send_replies: When True, messages will be sent to the submission
            author when comments are made to the submission (Default: True).
        :returns: A :class:`~.Submission` object for the newly created
            submission.

        Either ``selftext`` or ``url`` can be provided, but not both.

        """
        if bool(selftext) == bool(url):
            raise TypeError('Either `selftext` or `url` must be provided.')

        data = {'sr': str(self), 'resubmit': bool(resubmit),
                'sendreplies': bool(send_replies), 'title': title}
        if selftext is not None:
            data.update(kind='self', text=selftext)
        else:
            data.update(kind='link', url=url)
        return self._reddit.post(API_PATH['submit'], data=data)


class SubredditFlair(object):
    """Provides a set of functions to interact with a Subreddit's flair."""

    def __init__(self, subreddit):
        """Create a SubredditFlair instance.

        :param subreddit: The subreddit whose flair to work with.

        """
        self._unique_counter = 0
        self.subreddit = subreddit

    def __iter__(self):
        """Iterate through the Redditors and their associated flair."""
        url = API_PATH['flairlist'].format(subreddit=str(self.subreddit))
        params = {'unique': self._unique_counter}
        self._unique_counter += 1
        for item in ListingGenerator(self.subreddit._reddit, url, None,
                                     params=params):
            yield item

    def delete_all(self):
        """Delete all Redditor flair in the Subreddit.

        :returns: List of dictionaries indicating the success or failure of
            each delete.

        """
        return self.update(x['user'] for x in self)

    def set(self, thing, text='', css_class=''):
        """Set flair for a Redditor or Submission.

        :param thing: An instance of Redditor or Submission, or a string. When
            a string is provided it will be treated as the name of a Redditor.
        :param text: The flair text to associate with the Redditor or
            Submission (Default: '').
        :param css_class: The css class to associate with the flair html
            (Default: '').

        This method can only be used by an authenticated user who is a
        moderator of the associated Subreddit.

        """
        data = {'css_class': css_class, 'text': text}
        if thing.__class__.__name__ == 'Submission':
            data['link'] = thing.fullname
        else:
            data['name'] = str(thing)
        url = API_PATH['flair'].format(subreddit=self.subreddit)
        self.subreddit._reddit.post(url, data=data)

    def update(self, flair_list, text='', css_class=''):
        """Set or clear the flair for many Redditors at once.

        :param redditor_flair_list: Each item in this list should be either: a
            Redditor name string, a Redditor, or a dictionary containing the
            keys ``user``, ``flair_text``, and ``flair_css_class``. The
            ``user`` key should map to a Redditor name string, or a
            Redditor. When a dictionary isn't provided, or the dictionary is
            missing one of ``flair_text``, or ``flair_css_class`` attributes
            the default values will come from the the following arguments.
        :param text: The flair text to use when not explicitly provided in
            ``flair_list`` (Default: '').
        :param css_class: The css class to use when not explicitly provided in
            ``flair_list`` (Default: '').
        :returns: List of dictionaries indicating the success or failure of
            each update.

        """
        lines = []
        for item in flair_list:
            if isinstance(item, dict):
                fmt_data = (str(item['user']), item.get('flair_text', text),
                            item.get('flair_css_class', css_class))
            else:
                fmt_data = (str(item), text, css_class)
            lines.append('"{}","{}","{}"'.format(*fmt_data))

        response = []
        url = API_PATH['flaircsv'].format(subreddit=str(self.subreddit))
        while len(lines):
            data = {'flair_csv': '\n'.join(lines[:100])}
            response.extend(self.subreddit._reddit.post(url, data=data))
            lines = lines[100:]
        return response


class SubredditModeration(object):
    """Provides a set of moderation functions to a Subreddit."""

    def __init__(self, subreddit):
        """Create a SubredditModeration instance.

        :param subreddit: The subreddit to moderate.

        """
        self.subreddit = subreddit

    def approve(self, thing):
        """Approve a Comment or Submission.

        :param thing: An instance of Comment or Submission.

        Approving a comment or submission reverts a removal, resets the report
        counter, adds a green check mark indicator (only visible to other
        moderators) on the website view, and sets the ``approved_by`` attribute
        to the authenticated user.

        """
        self.subreddit._reddit.post(API_PATH['approve'],
                                    data={'id': thing.fullname})

    def distinguish(self, thing, how='yes'):
        """Distinguish a Comment or Submission.

        :param thing: An instance of Comment or Submission.

        :param how: One of 'yes', 'no', 'admin', 'special'. 'yes' adds a
            moderator level distinguish. 'no' removes any distinction. 'admin'
            and 'special' require special user priviliges to use.

        """
        return self.subreddit._reddit.post(
            API_PATH['distinguish'], data={'how': how, 'id': thing.fullname})

    def ignore_reports(self, thing):
        """Ignore future reports on a Comment or Submission.

        :param thing: An instance of Comment or Submission.

        Calling this method will prevent future reports on this Comment or
        Submission from both triggering notifications and appearing in the
        various moderation listings. The report count will still increment on
        the Comment or Submission.

        """
        self.subreddit._reddit.post(API_PATH['ignore_reports'],
                                    data={'id': thing.fullname})

    def remove(self, thing, spam=False):
        """Remove a Comment or Submission.

        :param thing: An instance of Comment or Submission.
        :param spam: When True, use the removal to help train the Subreddit's
            spam filter (Default: False)

        """
        data = {'id': thing.fullname, 'spam': bool(spam)}
        self.subreddit._reddit.post(API_PATH['remove'], data=data)

    def undistinguish(self, thing):
        """Remove mod, admin or special distinguishing on object.

        :returns: The json response from the server.

        """
        return self.distinguish(thing, how='no')

    def unignore_reports(self, thing):
        """Resume receiving future reports on a Comment or Submission.

        :param thing: An instance of Comment or Submission.

        Future reports on this Comment or Submission will cause notifications,
        and appear in the various moderation listings.

        """
        self.subreddit._reddit.post(API_PATH['unignore_reports'],
                                    data={'id': thing.fullname})


class SubredditRelationship(object):
    """Represents a relationship between a redditor and subreddit."""

    def __init__(self, subreddit, relationship):
        """Create a SubredditRelationship instance.

        :param subreddit: The subreddit for the relationship.
        :param relationship: The name of the relationship.

        """
        self.relationship = relationship
        self.subreddit = subreddit
        self._unique_counter = 0

    def __iter__(self):
        """Iterate through the Redditors belonging to this relationship."""
        url = API_PATH[self.relationship].format(subreddit=str(self.subreddit))
        params = {'unique': self._unique_counter}
        self._unique_counter += 1
        for item in self.subreddit._reddit.get(url, params=params):
            yield item

    def add(self, redditor):
        """Add ``redditor`` to this relationship.

        :param redditor: A string or :class:`~.Redditor` instance.

        """
        data = {'name': str(redditor), 'r': str(self.subreddit),
                'type': self.relationship}
        return self.subreddit._reddit.post(API_PATH['friend'], data=data)

    def remove(self, redditor):
        """Remove ``redditor`` from this relationship.

        :param redditor: A string or :class:`~.Redditor` instance.

        """
        data = {'name': str(redditor), 'r': str(self.subreddit),
                'type': self.relationship}
        return self.subreddit._reddit.post(API_PATH['unfriend'], data=data)


class SubredditStream(object):
    """Provides submission and comment streams."""

    def __init__(self, subreddit):
        """Create a SubredditStream instance.

        :param subreddit: The subreddit associated with the streams.

        """
        self.subreddit = subreddit

    def comments(self):
        """Yield new comments as they become available.

        Comments are yielded oldest first. Up to 100 historial comments will
        initially be returned.

        """
        before_fullname = None
        seen_fullnames = BoundedSet(100)
        without_before_counter = 0
        while True:
            newest_fullname = None
            limit = 100
            if before_fullname is None:
                limit -= without_before_counter
                without_before_counter = (without_before_counter + 1) % 30
            for comment in reversed(list(self.subreddit.comments(
                    limit=limit, params={'before': before_fullname}))):
                if comment.fullname in seen_fullnames:
                    continue
                seen_fullnames.add(comment.fullname)
                newest_fullname = comment.fullname
                yield comment
            before_fullname = newest_fullname