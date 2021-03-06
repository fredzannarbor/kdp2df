import pandas as pd
import glob
import os
import matplotlib.pyplot as plt
import argparse 
import numpy as np
from forex_python.converter import CurrencyRates
import datetime
import time

parser = argparse.ArgumentParser()
parser.add_argument("--infile", help = "seed file", default = 'select_criteria/isbns')
parser.add_argument("--outfile", help = "path to outfile", default = 'results.xlsx')
parser.add_argument("--lsipath", help = "path to lsi yearly folder", default = '.')

args = parser.parse_args()

input_file = args.infile
output_file = args.outfile
lsipath = args.lsipath

mrr = 1500

myfile = open(input_file, 'r')
select_criteria = myfile.readlines()
print('criteria file was ', input_file)

#df = pd.DataFrame()

today = pd.to_datetime("today")
c = CurrencyRates()
cgbp = c.get_rate('GBP', 'USD')

historic = pd.read_csv('exchangerates/historic.csv') # historic currency rates
historic.rename(columns = {'Unnamed: 0': 'Date'}, inplace = True)
historic.set_index('Date', inplace=True)

df = pd.DataFrame()
for i in glob.glob(r'lsidata/*.xls'):
    #print(i)
    data = pd.read_csv(i, sep='\t', lineterminator='\r', encoding='cp1252')
    yearval = os.path.splitext(i)[0]
    
    lasttwo = yearval[-2:]
    if  lasttwo == "UK" :
        yearval = yearval[:-2]
        #print('read data for UK ', yearval)
    elif  lasttwo == "GC" :
        #print(lasttwo, 'lasttwo')
        yearval = yearval[:-2]
        #print('read data from Global Connect file', lasttwo)
    else:
        pass
    data.insert(1, 'year', yearval)
    data = data[:-1] #necessary to remove extra lines
    df = df.append(data, ignore_index=True)

print('read LSI data and created dataframe')
 
# now read data in KDP Prior Months Royalties report format 
#  initially supports only post-2015 format

dkdp = pd.DataFrame()

for i in glob.glob(r'kdpdata/*.xlsx'):
    print("i is", i)
    kdpdata = pd.read_excel(i)
    kdpdate = kdpdata.columns[1]
    kdpdata = pd.read_excel(i, header=1)
    
    # get month & date from file
    
    kdpdata['month'] = kdpdate.split()[0]
    kdpdata['year'] = kdpdate.split()[1]
    long_month_name = kdpdate.split()[0]
    year_name = kdpdate.split()[1]
    month_number = datetime.datetime.strptime(long_month_name, "%B").month
    year_number  = datetime.datetime.strptime(year_name, "%Y").year
    exchangedate = datetime.datetime(year_number, month_number, 1)
    lookupdate = exchangedate.strftime('%F')
    cusd = 1.0
    cgbp = historic.loc[lookupdate, 'GBP']
    ceur = historic.loc[lookupdate, 'EUR']
    cjpy = historic.loc[lookupdate, 'JPY']
    caud = historic.loc[lookupdate, 'AUD']
    ccad = historic.loc[lookupdate, 'CAD']
    cbrl = historic.loc[lookupdate, 'BRL']
    cmxn = historic.loc[lookupdate, 'MXN']
    cinr = historic.loc[lookupdate, 'INR']
    #cgbp = historic[historic['Date'] == lookupdate]['GBP']

    conditions = [ 
        kdpdata['Currency'] == 'USD',
        kdpdata['Currency'] == 'GBP',
        kdpdata['Currency'] == 'EUR',
        kdpdata['Currency'] == 'JPY',
        kdpdata['Currency'] == 'AUD',
        kdpdata['Currency'] == 'CAD',
        kdpdata['Currency'] == 'BRL',
        kdpdata['Currency'] == 'MXN',
        kdpdata['Currency'] == 'INR']

    choices = [ 
        kdpdata['Royalty'] * cusd,
        kdpdata['Royalty'] * cgbp,
        kdpdata['Royalty'] * ceur,
        kdpdata['Royalty'] * cjpy,
        kdpdata['Royalty'] * caud,
        kdpdata['Royalty'] * ccad,
        kdpdata['Royalty'] * cbrl,
        kdpdata['Royalty'] * cmxn,
        kdpdata['Royalty'] * cinr
        ]

    kdpdata['USDeq_Royalty'] = np.select(conditions, choices, default=0)
    kdpdata['USDeq_Royalty'] = kdpdata['USDeq_Royalty'].round(2)
    # add column with exchange rate



    dkdp = dkdp.append(kdpdata, ignore_index=True)



netunits = dkdp.groupby(['Title'], as_index=False)[['Title', 'Net Units Sold']].sum().sort_values(by='Net Units Sold', ascending = False)
print(dkdp['month'].value_counts())
print('unique ASINs with sales', dkdp['ASIN'].nunique())



pubdates = pd.read_csv('BIPtruth.csv')
pubdates = pubdates.replace({'TRUE':True,'FALSE':False})
#print('pubdates', pubdates)

list = ['Pub Date', 'isbn_13', 'title', 'product_line', 'royaltied', 'public_domain_work']
subpub = pubdates[list]
today = pd.to_datetime("today")
subpub['Pub Date'] = pd.to_datetime(subpub['Pub Date'])
subpub['pub_age'] = today - subpub['Pub Date']
subpub['lmip'] = subpub['pub_age'] / np.timedelta64(1, 'M')
subpub['lmip'] = subpub['lmip'].round(2)
print('subpub', subpub)
#print(pubdates)
df['USDeq_pub_comp'] = np.where(df['reporting_currency_code']== 'GBP', (df['YTD_pub_comp'] * cgbp).round(2), df['YTD_pub_comp'])


df['YTD_net_quantity'] = df['YTD_net_quantity'].fillna(0.0).astype(int)
df['isbn_13'] = df['isbn_13'].fillna(0).astype(int)
df['YTD_net_quantity'].fillna(0.0).astype(int)
df['YTD_pub_comp'].fillna(0.0).astype(int)
df['USDeq_pub_comp'].fillna(0.0).astype(int)


## this merge is adding duplicate rows

enhanced = pd.merge(df, subpub, on='isbn_13', how = 'outer')

pd.set_option('max_colwidth', 25)

enhanced.set_index(['isbn_13'])

print('---')
print('enhanced')
print(enhanced)



LTD = enhanced.groupby(['title_x', 'lmip', 'author', 'isbn_13', 'product_line', 'royaltied', 'public_domain_work', 'year'], as_index=False)[['title_x', 'YTD_net_quantity', 'USDeq_pub_comp']].sum()
LTD['monthly_avg_$'] = (LTD['USDeq_pub_comp'] / LTD['lmip']).round(2)
print('---')
print('LTD')

print(LTD.sort_values(by='monthly_avg_$', ascending=False))
print('\n', 'LTD describe', '\n')
print(LTD.describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]))
LTD.to_csv('LTD.csv')
print('---')
print('frontlist')
frontlist = LTD[LTD['lmip'] < 12.0].sort_values(by='monthly_avg_$', ascending=False)
frontlist_number = (LTD[LTD['lmip'] < 12.0]).isbn_13.size

print(frontlist)
print(frontlist.describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]))
winsorized = (frontlist['USDeq_pub_comp'] > frontlist['USDeq_pub_comp'].quantile(0.05)) & (frontlist['USDeq_pub_comp'] < frontlist['USDeq_pub_comp'].quantile(0.95))
print('winsorized', frontlist[winsorized].describe(()))
frontlist.to_csv('frontlist.csv')
winsorized_mean = frontlist[winsorized]['monthly_avg_$'].mean()

print('\n', 'product lines')

productline = LTD.groupby('product_line').sum().sort_values(by='monthly_avg_$',ascending=False)
    
print(productline)

pd.set_option('display.max_rows', 1000)
pivotall = enhanced.pivot_table(index='title_x', columns='year', values='USDeq_pub_comp', aggfunc='sum', margins=True).sort_values(by='All', ascending=False)
print(pivotall)


pt2 = enhanced.pivot_table(index='isbn_13', columns='year', values='USDeq_pub_comp', aggfunc='sum', margins=True).sort_values(by='All', ascending=False)
pt2 = pd.merge(pt2, subpub, on='isbn_13', how='left')
pt2 = pt2[pt2['public_domain_work'].fillna(False)]


print('--')
print('public domain title performance')


pt2['monthly_avg_$'] = (pt2['All'] / pt2['lmip']).round(2)
colz = ['title', 'All', 'lmip', 'public_domain_work', 'monthly_avg_$']
print(pt2[colz].sort_values(by='monthly_avg_$', ascending=False))
print(pt2[colz].sort_values(by='All', ascending=False))

#winsorized_pt2 = (pt2['USDeq_pub_comp'] > pt2['USDeq_pub_comp'].quantile(0.05)) & (pt2['USDeq_pub_comp'] < pt2['USDeq_pub_comp'].quantile(0.95))
#print('winsorized public domain', pt2.describe(()))
frontlist.to_csv('frontlist.csv')


print(pt2[colz].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]))

#print(pt2.groupby('product_line').size())
#print(pt2.groupby('product_line').size().reset_index(name='counts'))
product_line = pt2.groupby('product_line').sum()
print(product_line.sort_values(by='monthly_avg_$', ascending=False))

print(' ')
print('Kindle Report')
print('most profitable Kindle titles')
print(dkdp.groupby('Title').sum().sort_values(by='USDeq_Royalty', ascending=False).head(10))

print('---')
print('dashboard')
print(' ')

mrr = 1500
goal = 10000
gap = goal - mrr
gap_titles_to_do = int(gap / winsorized_mean)

LSI_YTDrev = pivotall.iloc[0,-2].round()
KDP_LTDrev = dkdp['USDeq_Royalty'].sum()
wmean = frontlist[winsorized]['monthly_avg_$'].mean()


print("Goal MRR: $10,000")
print("Current MRR: ", f"${mrr:,.0f}")
print("Gap: ", f"${gap:,.0f}")
print("YTD LSI DEq earnings: ", f"${LSI_YTDrev:,.0f}")
print("LTD KDP DEq earnings: ", f"${KDP_LTDrev:,.0f}")
print("unique ASINs with sales: ", dkdp['ASIN'].nunique())
print("Net KDP unit sales: ", dkdp['Net Units Sold'].sum())

print("new LSI titles in last twelve months: ", frontlist_number)
print("monthly avg contribution of new titles: ", frontlist['monthly_avg_$'].sum().round(2))

print("Winsorized mean revenue per frontlist title: ", f"${wmean:,.2f}")

print('New titles needed until goal: ', gap_titles_to_do)
#print("Winsorized mean revenue per public domain title")
print()


