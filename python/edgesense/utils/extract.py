from datetime import datetime
import time
import logging

def identity_map(data):
    return data

def nested_objects_map(root_name, object_name):
    def nested_map(data):
        return [d[object_name] for d in data[root_name]]
    return nested_map

methods = { 
    'identity': {
        'users':    identity_map,
        'nodes':    identity_map, 
        'comments': identity_map
    },
    'nested': {
        'users':    nested_objects_map('users', 'user'),
        'nodes':    nested_objects_map('nodes', 'node'), 
        'comments': nested_objects_map('comments', 'comment') 
    },
    
}

def is_team(user, admin_roles):
    if user.has_key('roles') and admin_roles:
        user_roles = set([e.strip() for e in user['roles'].split(",") if e.strip()])
        return len(user_roles & admin_roles)>0
    else:
        return user.has_key('roles') and user['roles']!=""
        
def extract(how, what, data):
    if methods.has_key(how) and methods[how].has_key(what):
        return methods[how][what](data)
    else:
        raise Exception("Extraction method %s / %s not implemented" % (how, what))

def normalized_data(allusers, allnodes, allcomments, node_title_field='uid', admin_roles=set()):

    # build a mapping of nodes (users) keyed on their id
    nodes_map = {}
    for user in allusers:
        if not nodes_map.has_key(user['uid']):
            user_data = {}
            user_data['id'] = user['uid']
            if user.has_key(node_title_field):
                user_data['name'] = user[node_title_field]
            else:
                user_data['name'] = "User %(uid)s" % user
            if user.has_key('link') and user['link']!='':
                user_data['link'] = user['link']    
            # timestamps
            user_data['created_ts'] = int(user['created'])
            user_data['created_on'] = datetime.fromtimestamp(user_data['created_ts']).date().isoformat()
            # team membership
            user_data['team'] = is_team(user, admin_roles)
            user_data['team_ts'] = user_data['created_ts'] if user_data['team'] else None # this would be different if we'd start from previous data dump
            user_data['team_on'] = user_data['created_on'] if user_data['team'] else None # this would be different if we'd start from previous data dump
            user_data['active'] = False
            nodes_map[user['uid']] = user_data
        else:
            print "User %(uid)s was alredy added to the map (??)" % user

    logging.info("nodes collected")  

    # build a mapping of posts keyed by their post id (nid)
    posts_map = {}
    for post in allnodes:
        if not posts_map.has_key(post['nid']):
            post_data = {}
            post_data['id'] = post['nid']
            # timestamps
            post_data['created_ts'] = int(post['created'])
            post_data['created_on'] = datetime.fromtimestamp(post_data['created_ts']).date().isoformat()
            # author (& team membership)
            if post.has_key('uid') and nodes_map.has_key(post['uid']):
                post_data['author_id'] = post['uid']
                author = nodes_map[post_data['author_id']]
                post_data['team'] = author['team'] and author['team_ts'] <= post_data['created_ts']
                # nodes_map[post_data['author_id']]['active'] = True
            else:
                post_data['author_id'] = None
                post_data['team'] = False
            # length
            post_data['length'] = 0
            if post.has_key('Full text'):
                post_data['length'] += len(post['Full text'])
            if post.has_key('title'):
                post_data['length'] += len(post['title'])
            posts_map[post_data['id']] = post_data
        else:
            print "Post %(nid)s was alredy added to the map (??)" % post

    logging.info("posts collected")  

    # build a mapping of comments keyed by their comment id
    comments_map = {}
    for comment in allcomments:
        if not comments_map.has_key(comment['cid']):
            comment_data = {}
            comment_data['id'] = comment['cid']
        
            # timestamps
            comment_data['created_ts'] = int(comment['created'])
            comment_data['created_on'] = datetime.fromtimestamp(comment_data['created_ts']).date().isoformat()
        
            # author (& team membership)
            if comment.has_key('uid') and nodes_map.has_key(comment['uid']):
                comment_data['author_id'] = comment['uid']
                author = nodes_map[comment_data['author_id']]
                comment_data['team'] = author['team'] and author['team_ts'] <= comment_data['created_ts']
            else:
                comment_data['author_id'] = None
                comment_data['team'] = False
        
            # author of the post & group id
            if comment.has_key('nid') and posts_map.has_key(comment['nid']):
                post = posts_map[comment['nid']]
                comment_data['post_author_id'] = post['author_id']
            else:
                comment_data['post_author_id'] = None
        
            # length
            comment_data['length'] = 0
            if comment.has_key('comment'):
                comment_data['length'] += len(comment['comment'])
            if comment.has_key('subject'):
                comment_data['length'] += len(comment['subject'])
        
            comments_map[comment['cid']] = comment_data
    
        else:
            print "Comment %(cid)s was alredy added to the map (??)" % comment
    
    # second pass over comments, connect the comments to the parent comment
    for comment in allcomments:
        if comments_map.has_key(comment['cid']):
            comment_data = comments_map[comment['cid']]
            # if the comment has a pid then it was a comment to a comment
            # otherwise it was a comment to a post and the recipient is
            # the author of the post
            if comment.has_key('pid') and comment['pid']!='0' and comment['pid']!='':
                if comments_map.has_key(comment['pid']):
                    comment_data['recipient_id'] = comments_map[comment['pid']]['author_id']
                else:
                    comment_data['recipient_id'] = None
            else:
                comment_data['recipient_id'] = comment_data['post_author_id']
            # # check if the comment recipient is on the team
            # if nodes_map.has_key(comment_data['recipient_id']) and not comment_data['team']:
            #     recipient = nodes_map[comment_data['recipient_id']]
            #     comment_data['team'] = recipient['team'] and recipient['team_ts'] <= comment_data['created_ts']
        else:
            print "Comment %(cid)s not found" % comment
    
    return nodes_map, posts_map, comments_map