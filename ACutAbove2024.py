import streamlit as st
import requests
import pandas as pd
import json
from functools import reduce
from time import strftime, localtime
from datetime import datetime
import numpy as np
import altair as alt
import IPython
import plotly.express as px
from pandas import json_normalize
import seaborn as sns
from sleeper_wrapper import League
from sleeper_wrapper import Players


####### setting some stuff up

st.set_page_config(page_title="A Cut Above")
st.title(":blue[A Cut Above 2024]")

leagueid = "1056751362819633152"

tab1, tab2, tab3, tab4 = st.tabs(["Overall", "Waivers","Players", "Managers"])

now = datetime.now()
now = now.strftime('%Y-%m-%d')


if  now > '2024-12-02': currentweek=14
elif now > '2024-11-25': currentweek=13
elif now > '2024-11-18': currentweek=12
elif now > '2024-11-11': currentweek=11
elif now > '2024-11-04': currentweek=10
elif now > '2024-10-28': currentweek=9
elif now > '2024-10-21': currentweek=8
elif now > '2024-10-14': currentweek=7
elif now > '2024-10-07': currentweek=6
elif now > '2024-09-30': currentweek=5
elif now > '2024-09-23': currentweek=4
elif now > '2024-09-16': currentweek=3
elif now > '2024-09-09': currentweek=2
else: currentweek=1

managers_alive = 19-currentweek

league = League(leagueid)

############################################# users

@st.cache_data(ttl=3600)
def load_users():
    # get all users in a particular league
    users = league.get_users()
    users = pd.DataFrame(users)
    return users

users = load_users()

userlist = users['user_id'].tolist() ## metadata has team name...maybe I can eventually get this to be fully automated

# initialize list of lists
data = [['Mat', 1], ['Jeff', 2], ['CJ', 3],['Leo', 4],['Kevin', 5],['Hunter', 6],['Kyle', 7], ['Nick', 8], \
['Jimmy', 9],['Jonathan', 10],['Jon', 11],['Harry', 12],['Ian', 13],['Brandon', 14],['Myles', 15],['Jordan', 16],['Shea', 17],['Ed', 18]]
  
# Create the pandas DataFrame
users_df = pd.DataFrame(data, columns=['Manager', 'roster_id'])

df = users_df.loc[users_df.index.repeat(17)].reset_index(drop=True)
df['Week'] = df.groupby(['Manager'])['Manager'].transform("cumcount")
df['Week'] = df['Week']+1
df = df.loc[(df['Week'] <= currentweek)]


############################################# rosters

@st.cache_data(ttl=3600)
def load_rosters():
    # get all rosters in a particular league
    rosters = league.get_rosters()
    rosters = pd.DataFrame(rosters)

    rosters[["fpts","fpts_against","fpts_against_decimal","fpts_decimal","losses","ppts","ppts_decimal","ties","total_moves","waiver_budget_used","waiver_position","wins","locked"]] = rosters['settings'].apply(pd.Series)

    rosters = pd.merge(rosters, users_df, left_on='roster_id', right_on='roster_id')
    rosters = rosters[['Manager', 'fpts','fpts_decimal','ppts','ppts_decimal','waiver_budget_used']]
    return rosters

rosters = load_rosters()



############################################# players

@st.cache_data(ttl=3600)
def load_players():
    # get all players
    players = Players()

    player_df= players.get_all_players()
    player_df=pd.DataFrame.from_dict(player_df,orient="index")


    player_df = player_df[["first_name","last_name","position","team","player_id"]].reset_index()
    player_df.rename(columns={'position': 'Position','team':'Team'},inplace=True)
    player_df['Position'] = player_df['Position'].astype('string').str.replace('NFLPosition.', '')
    player_df['Team'] = player_df['Team'].astype('string').str.replace('NFLTeam.', '')
    return player_df

player_df = load_players()

############################################# matchups

@st.cache_data(ttl=3600)
def load_matchups():
    all_matchups1=pd.DataFrame()
    for i in range(1,currentweek+1): #gotta automate!
        data = league.get_matchups(i)
        data1 = pd.DataFrame(data)
        data1['Week'] = i
        frames = [all_matchups1,data1]
        all_matchups1= pd.concat(frames)
    return all_matchups1

all_matchups1 = load_matchups()


all_matchups2 = pd.merge(all_matchups1, users_df, left_on='roster_id', right_on='roster_id')
all_matchups = pd.merge(df, all_matchups2, on=['Manager','Week'],how='left')



all_matchups['Teams_Alive'] = 19-all_matchups['Week']
all_matchups["WeekRank"] = all_matchups.groupby("Week")["points"].rank(method="dense", ascending=False)
all_matchups['players_points'] = all_matchups['players_points'].astype('string')
all_matchups['Status'] = np.where((all_matchups['WeekRank']==all_matchups['Teams_Alive']) & (all_matchups['Week']<currentweek) , "Eliminated",\
                                  np.where((all_matchups['WeekRank']>all_matchups['Teams_Alive']) & (all_matchups['Week']<currentweek), "Out", \
                                           np.where((all_matchups['Week']==currentweek) & (all_matchups['players_points']=='{}'), "Out", \
                                                np.where(all_matchups['Week']==currentweek, "In Play","Alive"))))


all_matchups['Status'] = all_matchups['Status'].replace("In Play", method="ffill")

all_matchups['Points'] = np.where((all_matchups['points'] == 0) & (all_matchups['Status'].isin(['Out'])), [None], all_matchups['points'])


all_matchups = all_matchups[["Week","Manager","Points","Status"]]
all_matchups['Week'] = all_matchups['Week'].astype('string')
all_matchups['Points'] = all_matchups['Points'].astype('string').astype('float')
all_matchups['Cumulative Points'] = all_matchups.groupby(['Manager'])['Points'].cumsum()
all_matchups['2-Week Rolling Avg'] = all_matchups.groupby('Manager')['Points'].transform(lambda x: x.rolling(2, 2).mean())
all_matchups['3-Week Rolling Avg'] = all_matchups.groupby('Manager')['Points'].transform(lambda x: x.rolling(3, 3).mean())
all_matchups['3-Week Rolling Avg'] = np.where(all_matchups['Week'] == '1',all_matchups['Points'], ##bring in week 1 and rolling week 2 to make full graph
        np.where(all_matchups['Week']=='2',all_matchups['2-Week Rolling Avg'],all_matchups['3-Week Rolling Avg']))
all_matchups["Rolling Rank"] = all_matchups.groupby("Week")["3-Week Rolling Avg"].rank(method="dense", ascending=False)

all_matchups['Week'] = all_matchups['Week'].astype(int)

weekly_points = px.line(all_matchups, x="Week", y="Points", color='Manager',title="Points by Week")
weekly_points_cumu = px.line(all_matchups, x="Week", y="Cumulative Points", color='Manager',title="Cumulative Points by Week")

all_matchups_manager = all_matchups

if all_matchups.loc[(all_matchups['Points'] >0) & (all_matchups['Week'] == currentweek), 'Manager'].shape[0] == managers_alive:  
    all_matchups = all_matchups
else:
    all_matchups = all_matchups.loc[(all_matchups['Week']< currentweek)]

all_matchups_box = all_matchups

weekly_dist = px.box(all_matchups_box, x="Week", y="Points",points="all",hover_data="Manager",title="Weekly Distribution") #px.strip take out boxes


#####waterfall table

order_df = all_matchups

order_df['outorder'] = np.where(order_df['Status'].isin(['Out']),1,0)
order_df['outorder2'] = order_df.groupby(['Manager'])['outorder'].cumsum()
order_df = order_df.drop_duplicates(subset=['Manager'], keep='last')
order_df = order_df.sort_values(by = ['outorder2', 'Cumulative Points'], ascending = [False, True], na_position = 'first')

manager_order = order_df['Manager'].tolist()


all_matchups_wide = all_matchups[["Week","Manager","Points"]]
all_matchups_wide = all_matchups_wide.pivot(index='Week', columns='Manager', values='Points')

all_matchups_wide = all_matchups_wide.reindex(columns=manager_order)

##waterfall color palette options
cm = sns.color_palette("blend:red,yellow,green", as_cmap=True) # option 1
def color_survived(val): # option 2
    color = 'red' if val<50 else 'yellow' if val<75 else 'green' if val>74 else 'white'
    return f'background-color: {color}'

############################################# transactions

@st.cache_data(ttl=3600)
def load_transactions():
    all_trans=pd.DataFrame()
    for i in range(1,currentweek+1): #gotta automate this
        data = league.get_transactions(i)
        data1 = pd.DataFrame(data)
        frames = [all_trans,data1]
        all_trans= pd.concat(frames)
    return all_trans

all_trans = load_transactions()

result = all_trans

result  = result.explode('adds')
result  = result.explode('drops')
result[['seq','waiver_bid','priority']] = result['settings'].apply(pd.Series)


result[['notes']] = result['metadata'].apply(pd.Series)
result['roster_ids'] = result['roster_ids'].astype('string')
result['roster_ids'] = result['roster_ids'] .apply(lambda x: x.strip('[]'))
result['roster_ids'] = result['roster_ids'].astype('int64')
result = pd.merge(result, users_df, left_on='roster_ids', right_on='roster_id')
result['type'] = result['type'].astype('string')
result['type'] = result['type'].replace(["TransactionType.WAIVER", "TransactionType.FREE_AGENT",""], ["Waiver","Free Agent","Commissioner"])
result['type'] = result['type'].fillna("commissioner")

result['status'] = result['status'].astype('string')
result['status'] = result['status'].replace(["TransactionStatus.COMPLETE", "TransactionStatus.FAILED"], ["Complete","Failed"])


result['status_updated'] = result['status_updated'].astype('string')
result['status_updated'] = result['status_updated'].str.replace(',', '')
result['status_updated'] = result['status_updated'].astype(float)
result['status_new'] = result['status_updated'].div(1000)

result['date2'] = pd.to_datetime((result['status_new']),unit='s',utc=True).map(lambda x: x.tz_convert('US/Pacific'))
result['date3'] = result['date2'].dt.date
result['day_of_week'] = result['date2'].dt.day_name()


conditions = [
    (result['date2'] < '2024-09-09'),
    (result['date2'] > '2024-12-02'),
    (result['date2'] > '2024-11-25'),
    (result['date2'] > '2024-11-18'),
    (result['date2'] > '2024-11-11'),
    (result['date2'] > '2024-11-04'),
    (result['date2'] > '2024-10-28'),
    (result['date2'] > '2024-10-21'),
    (result['date2'] > '2024-10-14'),
    (result['date2'] > '2024-10-07'),
    (result['date2'] > '2024-09-30'),
    (result['date2'] > '2024-09-23'),
    (result['date2'] > '2024-09-16'),
    (result['date2'] > '2024-09-09')
    ]


#values = ['1','5','4','3','2']
values = [1,14,13,12,11,10,9,8,7,6,5,4,3,2]

result['week'] = np.select(conditions, values) #as defined above

added_df = pd.merge(result, player_df, left_on='adds', right_on='player_id')
added_df['Name'] = added_df['first_name'] + ' ' + added_df['last_name']


############ cumulative transactions

transactions_df = added_df[['week','Manager','Name','Position','Team','type','status','waiver_bid','notes']].query("status == 'complete'")
transactions_df['week'] = transactions_df['week'].astype(int)

week_manager_df = pd.merge(df,all_matchups_manager, on=['Week','Manager'],how='left')
trans_summary = transactions_df.query("type == 'waiver' & week != '1'").groupby(['week','Manager']).agg(WinningBids=('waiver_bid', 'count'),MoneySpent=('waiver_bid', 'sum'),MaxPlayer=('waiver_bid', 'max'),MedianPlayer=('waiver_bid', 'median')).reset_index()
trans_summary['week'] = trans_summary['week'].astype(int)


week_manager_df = pd.merge(week_manager_df, trans_summary,left_on=['Week','Manager'], right_on=['week','Manager'],how='left')
week_manager_df['Week'] = week_manager_df['Week'].astype(int)

week_manager_df['MoneySpent'] = np.where((week_manager_df['MoneySpent'].isnull()), 0, week_manager_df['MoneySpent'])
week_manager_df['Cumulative Spend'] = week_manager_df.groupby(['Manager'])['MoneySpent'].cumsum()
week_manager_df['Remaining Budget'] = np.where((week_manager_df['Status'].isin(['Out'])), 0, (1000-week_manager_df['Cumulative Spend']))
week_manager_df['Weeks_Alive'] = week_manager_df.groupby(['Manager'])['Points'].transform("count")
week_manager_df['Total Budget'] = week_manager_df.groupby(['Week'])['Remaining Budget'].transform("sum")
week_manager_df['Budget Percent'] = week_manager_df['Remaining Budget']/week_manager_df['Total Budget']
week_manager_df = week_manager_df.sort_values(by =['Week','Remaining Budget','Weeks_Alive'],ascending=[False,True,True])



week_manager_df_chart = week_manager_df.loc[(week_manager_df['Week']>1)]
manager_position_df = transactions_df.query("type == 'waiver'").groupby(['Position','Manager']).agg(WinningBids=('waiver_bid', 'count'),MoneySpent=('waiver_bid', 'sum'),MaxPlayer=('waiver_bid', 'max'),MedianPlayer=('waiver_bid', 'median')).reset_index()
week_position_df = transactions_df.query("type == 'waiver' & week >1").groupby(['week','Position']).agg(WinningBids=('waiver_bid', 'count'),MoneySpent=('waiver_bid', 'sum'),MaxPlayer=('waiver_bid', 'max'),MedianPlayer=('waiver_bid', 'median')).reset_index()
week_budget_df = week_manager_df.groupby(['Week']).agg(RemainingBudget=('Remaining Budget', 'sum')).reset_index()


week_overall_df = transactions_df.query("type == 'waiver'").groupby(['week']).agg(WinningBids=('waiver_bid', 'count'),MoneySpent=('waiver_bid', 'sum'),MaxPlayer=('waiver_bid', 'max'),MedianPlayer=('waiver_bid', 'median')).reset_index()
position_overall_df = transactions_df.query("type == 'waiver'").groupby(['Position']).agg(WinningBids=('waiver_bid', 'count'),MoneySpent=('waiver_bid', 'sum'),MaxPlayer=('waiver_bid', 'max'),MedianPlayer=('waiver_bid', 'median')).reset_index()

###budget charts
week_manager_budget = px.area(week_manager_df, x="Week", y="Budget Percent", color='Manager',title="Budget Percent by Week").update_xaxes(type='category', categoryorder='category ascending') ##changed from line chart
week_budget_chart = px.bar(week_budget_df, x="Week", y="RemainingBudget",text_auto='.2s',title="Overall Budget Remaining by Week")

############# adds

adds_df = added_df.groupby(['Manager','Name','Position','Team','type','status','adds','week','waiver_bid','notes'])['leg'].count().reset_index(name="Count")

manager_player_success = adds_df.query("status == 'complete'").groupby(['Manager','Name','Position','Team','type','week'])['waiver_bid'].max().reset_index(name="Winning Bid")
manager_player_fail = adds_df.query("notes == 'This player was claimed by another owner.'").groupby(['Manager','Name','Position','Team','type','week'])['waiver_bid'].count().reset_index(name="Losing Bids")
manager_player_fail_max = adds_df.query("notes == 'This player was claimed by another owner.'").groupby(['Manager','Name','Position','Team','type','week'])['waiver_bid'].max().reset_index(name="Max Losing Bid")
#manager_player_roster = adds_df.groupby(['Manager','Name','Position','Team','type','week'])['notes'].apply(lambda x: (x=='Unfortunately, your roster will have too many players after this transaction.').sum()).reset_index(name='No Space Count')
manager_player_roster = adds_df.query("notes == 'Unfortunately, your roster will have too many players after this transaction.'").groupby(['Manager','Name','Position','Team','type','week']).agg(NoSpaceCount=('waiver_bid', 'count'),NoSpaceMax=('waiver_bid', 'max')).reset_index()

adds_dataframes = [manager_player_success,manager_player_fail, manager_player_fail_max,manager_player_roster]


adds_df_combined = reduce(lambda df1,df2: pd.merge(df1,df2,on=['Manager', 'Name','Position','Team','type','week'],how='outer'), adds_dataframes)
adds_df_combined['Losing Bids'] = np.where((adds_df_combined['Winning Bid'] > 0), [None], adds_df_combined['Losing Bids'])
adds_df_combined['Max Losing Bid'] = np.where((adds_df_combined['Winning Bid'] > 0), [None], adds_df_combined['Max Losing Bid'])


adds_player = adds_df_combined.query("type == 'waiver'").groupby(['week','Name','Position','Team']) \
    .agg(Bids=('Position', 'count'),WinningBid=('Winning Bid', 'max'),LosingBids=('Losing Bids', 'count'), LosingAmounts=('Max Losing Bid', 'sum'),\
         LosingMax=('Max Losing Bid', 'max'),LosingMin=('Max Losing Bid', 'min'),LosingAvg=('Max Losing Bid', 'mean'),LosingMedian=('Max Losing Bid', 'median')).reset_index()

adds_player = adds_player[adds_player['WinningBid'].notna()]
adds_player = adds_player.sort_values(by='WinningBid',ascending=False)
adds_player['Difference'] = adds_player['WinningBid'] - adds_player['LosingMax']

##bring in manager for top and second-highest bid
adds_manager = adds_df.query("notes !='Unfortunately, your roster will have too many players after this transaction.'")[['Name','Manager','week','waiver_bid','status']]

adds_player = pd.merge(adds_player, adds_manager, left_on=['week','Name','WinningBid'], right_on=['week','Name','waiver_bid'],how='left').drop_duplicates().reset_index(drop=True)
adds_player = adds_player.loc[(adds_player['status']=='complete')]
adds_player = pd.merge(adds_player, adds_manager, left_on=['week','Name','LosingMax'], right_on=['week','Name','waiver_bid'],how='left').drop_duplicates().reset_index(drop=True)
adds_player['check_dupes'] = adds_player.duplicated(subset=['week','Name','Manager_x','waiver_bid_x'], keep=False).astype(int).astype(float)

##dedupe for bids where multiple people had second highest
adds_duped = np.where(adds_player['check_dupes']==1)
adds_duped = adds_player.query("check_dupes==1")
adds_duped['CUM_CONCAT']=[y.Manager_y.tolist()[:z+1] for x, y in adds_duped.groupby(['week','Name','Manager_x','waiver_bid_x'])for z in range(len(y))]
adds_duped['CUM_CONCAT'] = adds_duped['CUM_CONCAT'].astype('string')
adds_duped['cum_bids'] = adds_duped.groupby(['week','Name','Manager_x','waiver_bid_x'])['check_dupes'].cumsum()
adds_duped = adds_duped.drop_duplicates(subset=['week','Name','Manager_x','waiver_bid_x'], keep='last')
adds_duped = adds_duped[['week','Name','Manager_x','CUM_CONCAT']]

adds_player = pd.merge(adds_player, adds_duped, left_on=['week','Name','Manager_x'], right_on=['week','Name','Manager_x'],how='left')
adds_player['Manager_y'] = np.where((adds_player['check_dupes']==1), adds_player['CUM_CONCAT'], adds_player['Manager_y'])
adds_player = adds_player.drop_duplicates(subset=['week','Name','Manager_x','waiver_bid_x'], keep='last')
adds_player = adds_player.drop(['waiver_bid_x', 'waiver_bid_y','check_dupes','CUM_CONCAT'], axis=1)
adds_player.rename(columns={'Manager_x': 'Winning Manager','Manager_y':'Runner-Up Manager'},inplace=True)


### gaps for winners and runners-up - maybe I should filter for managers still alive?
bids_winning = adds_player.groupby(['Winning Manager']) \
    .agg(AvgGap=('Difference', 'mean'),MedianGap=('Difference', 'median'),\
         MaxGap=('Difference', 'max'),MinGap=('Difference', 'min')).reset_index()

bids_runnerup = adds_player.groupby(['Runner-Up Manager']) \
    .agg(AvgGap=('Difference', 'mean'),MedianGap=('Difference', 'median'),\
         MaxGap=('Difference', 'max'),MinGap=('Difference', 'min')).reset_index()

#bar = st.radio("Choose Metric:", ['AvgGap','MedianGap','MaxGap','MinGap']) ##where does this go?
#wingap_chart = px.bar(bids_winning, x="Winning Manager", y=bar,text_auto='.2s').update_layout(title=bar+" by Manager, Winning Bids",barmode='stack', xaxis={'categoryorder':'total descending'})
#st.plotly_chart(wingap_chart, theme=None,use_container_width=True)   
#wingap_chart = px.bar(bids_runnerup, x="Runner-Up Manager", y=bar,text_auto='.2s').update_layout(title=bar+" by Manager, Runner-Up Bids",barmode='stack', xaxis={'categoryorder':'total descending'})
#st.plotly_chart(wingap_chart, theme=None,use_container_width=True)  


adds_player_summary = adds_player.groupby(['Name','Position','Team']) \
    .agg(Pickups=('Bids','count'),AvgBids=('Bids','mean'),MoneySpent=('WinningBid','sum'),AvgSpent=('WinningBid','mean')).reset_index()

adds_player_summary = adds_player_summary.loc[adds_player_summary['Pickups']>1]
adds_player_summary = adds_player_summary.sort_values(by = ['Pickups', 'AvgSpent'], ascending = [False, False], na_position = 'first')

##multi-adds chart
adds_player_chart = adds_player.sort_values(by='week',ascending=True)
adds_player_chart['Counter'] = adds_player_chart.groupby(['Name'])['Name'].transform("cumcount")
adds_player_chart['Counter'] = adds_player_chart['Counter']+1
adds_player_chart['Pickups'] = adds_player_chart.groupby(['Name'])['Name'].transform("count")

adds_player_chart = adds_player_chart.loc[adds_player_chart['Pickups']>1]

### what's the correct line? I put difference at 30% of winning bid
waiver_scatter = px.scatter(adds_player, x="WinningBid", y="Difference",size="Bids", color="Bids",hover_data=["Name","Winning Manager","Runner-Up Manager"],title="Waiver Bids")\
    .add_shape(type="line",x0=0, y0=0, x1=max(adds_player['WinningBid']), y1=max(adds_player['WinningBid'])*.3,line=dict(color="MediumPurple",width=4,dash="dot"))

##player tree map
player_tree = px.treemap(adds_player, path=['Position', 'Name'], values='WinningBid',
                  color='Position', hover_data=['Name'],title="Tree Map of Waivers by Position")

player_tree.data[0].textinfo = 'label+text+value'

############# drops
dropped_df = pd.merge(result, player_df, left_on='drops', right_on='player_id')
dropped_df['Name'] = dropped_df['first_name'] + ' ' + dropped_df['last_name']
eliminated_df = dropped_df.loc[dropped_df['type'] == 'commissioner']
released_df = dropped_df.loc[(dropped_df['type'].isin(['waiver','free_agent'])) & (dropped_df['status'] =='complete')]

eliminated_summary = eliminated_df.groupby(['Name','Position','Team'])['leg'].count().sort_values(ascending=False).reset_index(name='Times Eliminated')
released_summary = released_df.groupby(['Name','Position','Team'])['leg'].count().sort_values(ascending=False).reset_index(name='Times Released')

dropped_summary = pd.merge(eliminated_summary, released_summary, on=['Name','Position','Team'], how='outer')
dropped_summary['Total'] = dropped_summary.fillna(0)['Times Eliminated']+dropped_summary.fillna(0)['Times Released']
dropped_summary = dropped_summary.sort_values(by = ['Total'], ascending = [False])

########## manager adds table

manager_waivers_df = transactions_df.query("type == 'waiver'").groupby(['Manager']).agg(WinningBids=('waiver_bid', 'count'),MoneySpent=('waiver_bid', 'sum'),MaxPlayer=('waiver_bid', 'max'),MedianPlayer=('waiver_bid', 'median')).reset_index()
manager_freeagents_df = transactions_df.query("type == 'free_agent'").groupby(['Manager'])['Manager'].count().reset_index(name="Free Agent Adds")
manager_losing_df = adds_df_combined.groupby(['Manager']).agg(LosingBids=('Losing Bids', 'count'),LosingBids2=('Losing Bids', 'sum'),NoSpaceBids=('NoSpaceCount', 'count'),NoSpaceBids2=('NoSpaceCount', 'sum'),\
                            LosingSum=('Max Losing Bid', 'sum'),SpaceSum=('NoSpaceMax', 'sum')).reset_index()
manager_weeks_df = week_manager_df.loc[week_manager_df['Week']== week_manager_df['Week'].max()]
manager_weeks_df = manager_weeks_df[['Manager','Weeks_Alive']]
                                     

adds_dataframes2 = [manager_waivers_df,manager_freeagents_df, manager_losing_df,manager_weeks_df]


manager_overall_df = reduce(lambda df1,df2: pd.merge(df1,df2,on=['Manager'],how='outer'), adds_dataframes2)

manager_overall_df['Average Bids'] = manager_overall_df.fillna(0)['WinningBids']/manager_overall_df['Weeks_Alive']
manager_overall_df['Average Spent'] = manager_overall_df.fillna(0)['MoneySpent']/manager_overall_df['Weeks_Alive']
manager_overall_df['Total Activity'] = manager_overall_df.fillna(0)['LosingBids2']+manager_overall_df.fillna(0)['NoSpaceBids2']+manager_overall_df.fillna(0)['WinningBids']+manager_overall_df.fillna(0)['Free Agent Adds']
manager_overall_df['Total Money Bid'] = manager_overall_df.fillna(0)['LosingSum']+manager_overall_df.fillna(0)['SpaceSum']+manager_overall_df.fillna(0)['MoneySpent']
manager_overall_df['Success Rate'] = manager_overall_df['WinningBids']/(manager_overall_df.fillna(0)['LosingBids']+manager_overall_df.fillna(0)['WinningBids'])

manager_overall_df = manager_overall_df[['Manager','Weeks_Alive','WinningBids','Average Bids','MoneySpent','Average Spent','MaxPlayer','MedianPlayer','LosingBids',\
                                         'Success Rate','Free Agent Adds','NoSpaceBids','Total Activity','Total Money Bid']].sort_values(by='WinningBids',ascending=False)


#####power rankings


#if week_manager_df.loc[(week_manager_df['Points']>0) & (week_manager_df['Week'] == currentweek), 'Manager'].shape[0] ==managers_alive:
#    power_rankings = week_manager_df.loc[(week_manager_df['Week']== currentweek) & (week_manager_df['Status']=='Alive')]

#else:
#    power_rankings = week_manager_df.loc[(week_manager_df['Week']== currentweek-1) & (week_manager_df['Status']=='Alive')]

power_rankings = week_manager_df.loc[(week_manager_df['Week']== currentweek) & (week_manager_df['Status']=='Alive')]


### messing around with a sliding weight for rolling score vs budget
power_rankings['rolling_z'] = (power_rankings['3-Week Rolling Avg'] - power_rankings['3-Week Rolling Avg'].mean())/power_rankings['3-Week Rolling Avg'].std(ddof=0)
power_rankings['budget_z'] = (power_rankings['Remaining Budget'] - power_rankings['Remaining Budget'].mean())/power_rankings['Remaining Budget'].std(ddof=0)
power_rankings['Power Ranking'] = power_rankings['rolling_z']*(14-currentweek)/14 + power_rankings['budget_z']*currentweek/14
#power_rankings["Power Ranking"] = power_rankings["Rank Sum"].rank(method="dense", ascending=False) #maybe keep this out for now?


power_rankings = power_rankings[['Manager','3-Week Rolling Avg','Remaining Budget','Power Ranking']].sort_values(by = 'Power Ranking',ascending=False)

#color palette options
cm_power = sns.light_palette("green", as_cmap=True)

##monthly points leaders

points_leaders = all_matchups

points_leaders_sep = points_leaders.query('Week in [1,2,3,4]').groupby(["Manager"])["Points"].sum().reset_index(name="September")
points_leaders_oct = points_leaders.query('Week in [5,6,7,8]').groupby(["Manager"])["Points"].sum().reset_index(name="October")
points_leaders_nov = points_leaders.query('Week in [9,10,11,12]').groupby(["Manager"])["Points"].sum().reset_index(name="November")


################ add automated text here

##overall tab

budget_left_text = format(min(week_budget_df['RemainingBudget']),',.0f')
alive_text = 19-currentweek

lost_teams_text = week_manager_df.loc[(week_manager_df['Status'].isin(['Out','Eliminated'])) & \
                                       (week_manager_df['Week'] == week_manager_df['Week'].max()), 'Manager']
lost_teams_text = list(lost_teams_text)
lost_teams_text = " and ".join([str(item) for item in lost_teams_text])

most_points_text = all_matchups.loc[all_matchups['Cumulative Points'] == all_matchups['Cumulative Points'].max(), 'Manager'].values[0]
most_rpoints_text = all_matchups.loc[(all_matchups['Rolling Rank'] == all_matchups['Rolling Rank'].min()) & \
                                     (all_matchups['Week'] == all_matchups['Week'].max()),'Manager'].values[0]

##waiver tab
week_manager_latest = week_manager_df.loc[week_manager_df['Week'] == currentweek]
most_budget_text = week_manager_latest.loc[(week_manager_latest['Remaining Budget'] == week_manager_latest['Remaining Budget'].max()), 'Manager'].values[0]

max_position_text = position_overall_df.loc[position_overall_df['MoneySpent'] == position_overall_df['MoneySpent'].max(), 'Position'].values[0]
position_spent_text = format(position_overall_df.loc[position_overall_df['MoneySpent'] == position_overall_df['MoneySpent'].max(), 'MoneySpent'].values[0],',.0f')
position_bids_text = position_overall_df.loc[position_overall_df['MoneySpent'] == position_overall_df['MoneySpent'].max(), 'WinningBids'].values[0]

##players tab
eliminated_most_text = eliminated_summary.loc[eliminated_summary['Times Eliminated'] == eliminated_summary['Times Eliminated'].max(), 'Name'].values[0]
eliminated_count_text = eliminated_summary.loc[eliminated_summary['Times Eliminated'] == eliminated_summary['Times Eliminated'].max(), 'Times Eliminated'].values[0]
eliminated_tie_text = eliminated_summary.loc[eliminated_summary['Times Eliminated'] == eliminated_summary['Times Eliminated'].max(), 'Times Eliminated'].shape[0]

released_most_text = released_summary.loc[released_summary['Times Released'] == released_summary['Times Released'].max(), 'Name'].values[0]
released_count_text = released_summary.loc[released_summary['Times Released'] == released_summary['Times Released'].max(), 'Times Released'].values[0]
released_tie_text = released_summary.loc[released_summary['Times Released'] == released_summary['Times Released'].max(), 'Times Released'].shape[0]

dropped_tie_text = dropped_summary.loc[dropped_summary['Total'] == dropped_summary['Total'].max(), 'Total'].shape[0]
dropped_count_text = format(dropped_summary.loc[dropped_summary['Total'] == dropped_summary['Total'].max(), 'Total'].values[0],'.0f')
dropped_most_text = dropped_summary.loc[dropped_summary['Total'] == dropped_summary['Total'].max(), 'Name'].values[0]


if eliminated_tie_text>1:
    elim = "{count} players have found themselves on the last place team {number} times. Maybe they were the problem?"\
         .format(count=eliminated_tie_text,number=eliminated_count_text)
else:
    elim = "{player} leads the way with {number} times being dropped from the last place team."\
         .format(player=eliminated_most_text,number=eliminated_count_text)

if released_tie_text>1:
    rele = "{count} players have been released a total of {number} times. These players are obviously good enough to be rostered but don't stick on a roster too long."\
         .format(count=released_tie_text,number=released_count_text)
else:
    rele = "{player} leads the way with {number} times being released."\
         .format(player=released_most_text,number=released_count_text)
    
if dropped_tie_text>1:
    drop = "{count} players have been dropped a total of {number} times."\
         .format(count=dropped_tie_text,number=dropped_count_text)
else:
    drop = "{player} leads the way with {number} times being dropped. Will anyone else take a chance on him?"\
         .format(player=dropped_most_text,number=dropped_count_text)
    

##manager tab

pr_top = power_rankings.loc[power_rankings['Power Ranking'] == power_rankings['Power Ranking'].max(), 'Manager'].values[0]
pr_bottom = power_rankings.loc[power_rankings['Power Ranking'] == power_rankings['Power Ranking'].min(), 'Manager'].values[0]

bid_text = manager_overall_df.loc[manager_overall_df['WinningBids'] == manager_overall_df['WinningBids'].max(), 'Manager'].values[0]
active_text = manager_overall_df.loc[manager_overall_df['Total Activity'] == manager_overall_df['Total Activity'].max(), 'Manager'].values[0]
money_text = manager_overall_df.loc[manager_overall_df['MoneySpent'] == manager_overall_df['MoneySpent'].max(), 'Manager'].values[0]
rate_text = manager_overall_df.loc[manager_overall_df['Success Rate'] == manager_overall_df['Success Rate'].max(), 'Manager'].values[0]
rate_text2 = manager_overall_df.loc[manager_overall_df['Success Rate'] == manager_overall_df['Success Rate'].min(), 'Manager'].values[0]

##################notes

# some players are slipping through the cracks on waiver summary charts; quentin johnston in the multi-add chart; something is going on with DK Metcalf too
# call out the most weekly wins, the most second places, the closest gaps between losing and surviging, the average and median gap ahead of last place, the most easy wins(at least x points ahead of last)")
# Show a chart with average and median gap for winning and runner-up bids...the charts are made but not included currently
# automate transactions date based on getting current date and using conditions set at the beginning
# eliminated players that haven't gotten picked back up
# table at top mapping manager to team name
# currently it doesnt register until everyone has points...could change?
# some chart axes show fractions...need to fix format
# some tables could use filtering options
# players that were selected on waivers but nobody else bid...show highest bids


#####analyses that require some research
#eventually I'd like to find a better table format to allow for filtering by manager etc
#can I find a place for a Race Chart?
#what about a ridgeplot?
#can I do anything with possible points? Who actually should have lost each week?
#it would be really cool to compare waiver price vs rest of season point totals for individual players - best values
# can I do something where I look at money spent on guys that were eventually dropped? Not for eliminated teams, but waiver/free agent moves where you drop a guy you spent big on.")

##### I took out tab5...maybe add back in the all_matchups table and any others that might be interesting to scroll through
#with tab5:
#st.header("TABLES!")
#st.image('https://44.media.tumblr.com/9a7e3822dd2771c1e7965542d7168ab1/b0ea9792e807e275-a6/s540x810_f1/e2bc4d208650b5c6a1751433189a529489e44df2.gif')
#st.write(all_matchups)


############################################################################################################

with tab1:
   st.header("Remaining Budget")
   st.write("We're into Week {theweek} and {teamcount} teams are still alive. The remaining overall budget has gone from 18K to {thebudget}."\
         .format(theweek=currentweek,teamcount=alive_text,thebudget=budget_left_text))
   st.plotly_chart(week_budget_chart, theme=None,use_container_width=True) ##reformat labels
   st.divider()
   st.header("Scoring")
   st.write("Here's how things have shaken out so far, with each score shaded relative to all scores over the full season. A big thanks to {losers} "\
            "for joining the league and letting us take their best players.".format(losers=lost_teams_text))
   st.dataframe(all_matchups_wide.style.format("{:.2f}").background_gradient(cmap=cm,axis=None).highlight_null('white')) ##need to figure out how to fit this all in without scrolling
   if most_points_text == most_rpoints_text:
    st.write("Below are charts showing points by week, rolling average, and cumulative. {mostpoints} has scored the most points so far and currently has the highest 3-week rolling average!"\
                .format(mostpoints=most_points_text))
   else:
    st.write("Below are charts showing points by week, rolling average, and cumulative. {mostpoints} has scored the most points so far, while {rolling} has the best 3-week rolling average."\
                .format(mostpoints=most_points_text,rolling=most_rpoints_text))
   line = st.radio("Choose Metric:", ['Points','3-Week Rolling Avg','Rolling Rank','Cumulative Points'])
   weekly_scoring_chart = px.line(all_matchups, x="Week", y=line, color="Manager",markers=True).update_layout(title="Manager "+line+" by Week").update_xaxes(type='category')
   st.plotly_chart(weekly_scoring_chart, theme=None,use_container_width=True)
   st.write("As the season has progressed, every team has steadily gotten better. The boxplots below show how the scores have been distributed each week. The average goes up, but so does the lowest score.")
   st.plotly_chart(weekly_dist, theme=None,use_container_width=True)

with tab2:
   st.header("Budget")
   st.write("It's great to be leading the way in remaining budget, as {budgetleader} currently is, but that also means other teams have "\
        "already bolstered their roster. It's a risky game to play. The chart below shows each manager's proportion of the total budget throughout the season."\
         .format(budgetleader=most_budget_text))
   st.plotly_chart(week_manager_budget, theme=None,use_container_width=True)
   st.divider()
   st.header("Waivers")
   st.write("Let's take a closer look at how waivers have gone this season. You can use the radio button to view money spent, number of winning bids, or max bid for each of the charts below.")
   bar = st.radio("Choose Metric:", ['MoneySpent','WinningBids','MaxPlayer'])
   st.write("The manager spend chart shows when and how much each manager has spent on shiny new toys.")
   week_manager_chart = px.bar(week_manager_df_chart, x="week", y=bar, color="Manager").update_layout(title="Manager "+bar+" by Week").update_xaxes(type='category')
   week_position_chart = px.bar(week_position_df, x="week", y=bar, color="Position").update_layout(title="Position "+bar+" by Week").update_xaxes(type='category')
   manager_position_chart = px.bar(manager_position_df, x="Manager", y=bar, color="Position").update_layout(title="Manager "+bar+" by Position")
   position_overall_chart = px.bar(position_overall_df, x="Position", y=bar,text_auto='.2s').update_layout(title=bar+" by Position")
   st.plotly_chart(week_manager_chart, theme=None,use_container_width=True)
   st.write("The {position} position has had the most money thrown its way, with {money} spent on {bids} waiver claims."\
         .format(position=max_position_text,money=position_spent_text,bids=position_bids_text))
   st.plotly_chart(position_overall_chart, theme=None,use_container_width=True)
   st.write("The position by manager chart shows how each manager has allocated their budget. The position by week chart follows closely to big names being dropped, especially at the quarterback and tight end positions.")
   st.plotly_chart(manager_position_chart, theme=None,use_container_width=True)
   st.plotly_chart(week_position_chart, theme=None,use_container_width=True)
   
   
with tab3:
   st.header("Adds")
   st.write("The tree chart below shows how much money has been spent on each player, grouped by position.") #Call out the top players for each, or maybe add a table below.
   st.plotly_chart(player_tree,use_container_width=True) #not sure I can get around multi-add players...so it's really cumulative by player
   st.write("This table shows all waiver claims so far this season, including the winning manager and runner-up manager for each.") ##maybe add free agent adds eventually
   st.dataframe(adds_player, hide_index=True) ## sort options: by difference to find closest and furthest...do callouts (wides and narrowest bid gaps)
   st.write("The chart and table below show the players that got picked up from waivers multiple times. How did their valuation change over the season?")
   line = st.radio("Choose Metric:", ['Bids','WinningBid'])
   multi_waiver_chart = px.line(adds_player_chart, x="Counter", y=line,markers=True, color="Name",hover_data=['week']).update_layout(title="Manager "+line+" by Week").update_xaxes(type='category')
   st.plotly_chart(multi_waiver_chart, theme=None,use_container_width=True)
   st.dataframe(adds_player_summary,hide_index=True) ##add total bids and number of free agent pickups
   st.write("This scatterplot looks at how close the waiver contests were. Dots below the line are closely-contested waivers, while ones above the line may have been overpays.")
   st.plotly_chart(waiver_scatter,use_container_width=True)
   st.divider()
   st.header("Drops")
   st.write(drop,elim,rele)
   st.dataframe(dropped_summary, hide_index=True) ##eventually filter for players dropped or released multiple times

with tab4:
   st.header("Power Rankings")
   st.write("To advance in this league, your team merely needs to be 'good enough'. But some teams have been scoring a ton of points each week and still have a healthy budget. ",\
    "Combining the remaining budget and 3-week scoring average, {top} is atop the power rankings. I'm still working on this formula, so let me know if you have any suggestions!"\
        .format(top=pr_top,bottom=pr_bottom))
   st.dataframe(power_rankings.style.format({'3-Week Rolling Avg': "{:.1f}",'Power Ranking': "{:.3f}",'Remaining Budget': "{:.0f}"}).\
                background_gradient(cmap=cm_power),hide_index=True,use_container_width=True)
   st.divider()
   st.header("Waivers")
   st.write("The table below summarizes how every manager has done on waivers. {bid} has won the most bids, {money} has spent the most money, "\
    "{rate} has the highest waiver success rate, and {rate2} has the lowest. {active} has been the most active on waivers, when including back-up bids that didn't get processed."\
        .format(bid=bid_text,money=money_text,rate=rate_text,rate2=rate_text2,active=active_text))
   st.dataframe(manager_overall_df, hide_index=True) #the only other thing I could add here is highest week of money spending; also, its huge - maybe split into two tables

