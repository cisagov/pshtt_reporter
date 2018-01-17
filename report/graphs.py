#!/usr/bin/env python

import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib as mpl
from mpl_toolkits.basemap import Basemap
from matplotlib.patches import Rectangle, Ellipse, RegularPolygon
from matplotlib.collections import PatchCollection
from matplotlib.ticker import MaxNLocator
from matplotlib.dates import DateFormatter
from textwrap import TextWrapper
from pandas import DataFrame, Series
import pandas as pd
from itertools import chain

# Blue, Green, Yellow, Orange, Red,
BLUE = '#5c90ba'
GREEN = '#7bbe5e'
YELLOW = '#cfc666'
ORANGE = '#cf9c66'
RED = '#c66270'
COLORS = (BLUE, YELLOW, ORANGE, RED, GREEN)  # vuln colors first, then green

DARK_BLUE = '#3c698e'
DARK_GREEN = '#56943c'
DARK_YELLOW = '#b1a738'
DARK_ORANGE = '#b17638'
DARK_RED = '#a13a49'
COLORS_DARK = (DARK_BLUE, DARK_YELLOW, DARK_ORANGE, DARK_RED, DARK_GREEN)

LIGHT_BLUE = '#92b5d1'
LIGHT_GREEN = '#a8d494'
LIGHT_YELLOW = '#e1dca0'
LIGHT_ORANGE = '#e1c2a0'
LIGHT_RED = '#e8c0c5'
COLORS_LIGHT = (LIGHT_BLUE, LIGHT_YELLOW, LIGHT_ORANGE, LIGHT_RED, LIGHT_GREEN)

GREY_LIGHT = '#e8e8e8'
GREY_MID = '#cecece'
GREY_DARK = '#a1a1a1'

PIE_COLORS = COLORS + COLORS_DARK + COLORS_LIGHT

TOO_SMALL_WEDGE = 30

# import IPython; IPython.embed() #<<<<<BREAKPOINT>>>>>>>


def setup():
    fig_width_pt = 505.89  # Get this from LaTeX using \showthe\columnwidth (see *.width file)
    inches_per_pt = 1.0 / 72.27  # Convert pt to inch
    golden_mean = (np.sqrt(5) - 1.0) / 2.0  # Aesthetic ratio
    fig_width = fig_width_pt * inches_per_pt  # width in inches
    fig_height = fig_width * golden_mean  # height in inches
    fig_size = [fig_width, fig_height]
    params = {'backend': 'pdf',
              # 'font.family': 'sans-serif',
              # 'font.sans-serif': ['Avenir Next'],
              'axes.labelsize': 10,
              'font.size': 10,
              'legend.fontsize': 8,
              'xtick.labelsize': 8,
              'ytick.labelsize': 8,
              'font.size': 10,
              'text.usetex': False,
              'figure.figsize': fig_size}
    plt.rcParams.update(params)


def wrapLabels(labels, width):
    wrapper = TextWrapper(width=width, break_long_words=False)
    result = []
    for label in labels:
        result.append(wrapper.fill(label))
    return result


class MyMessage(object):
    def __init__(self, message):
        self.message = message

    def plot(self, filename, size=1.0):
        fig = plt.figure(1)
        fig.set_size_inches(fig.get_size_inches() * size)
        ax = fig.add_subplot(1, 1, 1)
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.text(0.5, 0.5, self.message,
                horizontalalignment='center',
                verticalalignment='center',
                fontsize=20 * size, color=DARK_GREEN,
                transform=ax.transAxes)
        plt.savefig(filename + '.pdf')
        plt.close()


class MyStackedBar(object):
    def __init__(self, data, ylabels, dataLabels):
        self.data = data
        self.ylabels = ylabels
        self.dataLabels = dataLabels

    def plot(self, filename, size=1.0):
        pos = np.arange(len(self.ylabels))[::-1]
        fig = plt.figure(1)
        fig.set_size_inches(fig.get_size_inches() * size)
        # fig.subplots_adjust(left=0.15, bottom=0.15)
        ax = fig.add_subplot(1, 1, 1)
        plt.xlabel('Vulnerabilities')

        majorLocator = MaxNLocator(nbins=5, integer=True)  # only mark integers
        ax.xaxis.set_major_locator(majorLocator)

        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.xaxis.tick_bottom()
        ax.yaxis.tick_left()

        lefts = [0] * len(self.ylabels)
        bars = []
        i = 0
        for dataset in self.data:
            p = ax.barh(pos, dataset, align='center', color=COLORS[i], edgecolor='white', left=lefts)
            lefts = map(lambda x, y: x + y, lefts, dataset)
            i += 1
            bars.append(p)

        plt.yticks(pos, self.ylabels, rotation=None, fontsize=8)
        try:
            leg = plt.legend(bars, self.dataLabels, ncol=len(self.dataLabels), loc='upper center', fancybox=True,
                             prop={'size': 4})
            leg.get_frame().set_alpha(0.5)
        except IndexError as e:
            pass
            # if there are no bars, the legend will throw a IndexError
            # it should be safe to ignore, but there will be no legend

        for bar in bars:
            for rect in bar:
                # Rectangle widths are already integer-valued but are floating
                # type, so it helps to remove the trailing decimal point and 0 by
                # converting width to int type
                width = int(rect.get_width())

                labelString = '{:,d}'.format(width)
                if (width > 0):  # TODO handle too labels getting squeezed, need box width in points
                    xloc = rect.get_x() + 0.5 * width
                    clr = 'white'
                    align = 'right'
                    yloc = rect.get_y() + rect.get_height() / 2.0  # Center the text vertically in the bar
                    ax.annotate(labelString, xy=(xloc, yloc), xycoords='data',
                                xytext=(-4, 0), textcoords='offset points',
                                size=12, va='center', weight='bold', color=clr
                                )

        ax.set_ylim([-0.5, 5])
        fig.set_tight_layout(True)
        plt.savefig(filename + '.pdf')
        plt.close()


class MyBar(object):
    def __init__(self, series, yscale='linear', bigLabels=False, barSeverities=None, legendLabels=None):
        self.series = series
        self.yscale = yscale
        self.bigLabels = bigLabels
        self.barSeverities = barSeverities
        self.legendLabels = legendLabels

    def plot(self, filename, size=1.0):
        fig = plt.figure(1)
        fig.set_size_inches(fig.get_size_inches() * size)

        if self.bigLabels:
            fig.subplots_adjust(bottom=0.4)

        ax = fig.add_subplot(1, 1, 1)
        ax.set_yscale(self.yscale)
        pos = np.arange(len(self.series))  # the bar centers on the x axis

        if self.barSeverities:
            barColors = []
            for i in self.barSeverities:
                barColors.append(COLORS[i - 1])
            if self.legendLabels:  # build a dummy set of bars ('underneath' the real bars) to be used
                legendColors = []  # to color the legend; legendLabels are implicitly tied to COLORS
                for i in range(len(self.legendLabels)):
                    legendColors.append(COLORS[i])
                dummy_legend_rects = plt.bar(pos, self.series.values, align='center', color=legendColors,
                                             edgecolor='white', width=0.5)
                leg = plt.legend(dummy_legend_rects, self.legendLabels, ncol=len(self.legendLabels), loc='upper center',
                                 fancybox=True, prop={'size': 4}, bbox_to_anchor=(0.5, 1.2))
                leg.get_frame().set_alpha(0.5)
            rects = plt.bar(pos, self.series.values, align='center', color=barColors, edgecolor='white', width=0.5)
        else:
            rects = plt.bar(pos, self.series.values, align='center', color=BLUE, edgecolor='white', width=0.5)

        if self.bigLabels:
            plt.xticks(pos, wrapLabels(self.series.index, 24), rotation=55, fontsize=7)
            # Extremely nice function to auto-rotate the x axis labels.
            # It was made for dates (hence the name) but it works
            # for any long x tick labels
            # fig.autofmt_xdate()
        else:
            plt.xticks(pos, wrapLabels(self.series.index, 6), rotation=None, fontsize=8)

        ax.yaxis.grid(False)
        ax.yaxis.tick_left()  # ticks only on left
        ax.yaxis.set_visible(False)
        ax.xaxis.tick_bottom()  # ticks only on bottom
        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        for rect in rects:
            # Rectangle widths are already integer-valued but are floating
            # type, so it helps to remove the trailing decimal point and 0 by
            # converting width to int type
            yloc = int(rect.get_height())
            xloc = rect.get_x() + rect.get_width() / 2.0  # Center the text horz in the bar

            # determine if the label should go in or above the bar
            display_coords = ax.transData.transform([xloc, yloc])
            axes_coords = ax.transAxes.inverted().transform(display_coords)

            if axes_coords[1] < 0.30:
                # above box
                color = 'black'
                offset = (0, 7)
            else:
                # in box
                color = 'white'
                offset = (0, -14)

            labelString = '{:,d}'.format(yloc)

            ax.annotate(labelString, xy=(xloc, yloc), xycoords='data',
                        xytext=offset, textcoords='offset points',
                        size=12, ha='center', weight='bold', color=color
                        )

        fig.set_tight_layout(True)
        plt.savefig(filename + '.pdf')
        plt.close()


class MyDistributionBar(object):
    def __init__(self, series, yscale='linear', xlabel=None, ylabel=None, final_bucket_accumulate=False,
                 x_major_tick_count=10, region_colors=[], x_limit_extra=0):
        self.series = series
        self.yscale = yscale
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.final_bucket_accumulate = final_bucket_accumulate
        self.x_major_tick_count = x_major_tick_count
        self.region_colors = region_colors
        self.x_limit_extra = x_limit_extra  # Used to add a little extra space to the end of the x axis to make the final bucket more readable

    def plot(self, filename, size=1.0):
        fig = plt.figure(figsize=(8, 2.75))
        fig.set_size_inches(fig.get_size_inches() * size)
        ax = fig.add_subplot(1, 1, 1)
        ax.set_yscale(self.yscale)
        pos = np.arange(len(self.series))  # the bar centers on the x axis
        # Manually set x-axis range to be between 0 and the highest value in the series plus any desired extra space (x_limit_extra)
        ax.set_xlim([0, self.series.index[-1] + self.x_limit_extra])

        if self.xlabel:
            plt.xlabel(self.xlabel)
        if self.ylabel:
            plt.ylabel(self.ylabel)

        tick_labels = list(self.series.index)
        if self.final_bucket_accumulate:
            tick_labels[-1] = '{}+'.format(tick_labels[-1])

        plt.bar(pos, self.series.values, tick_label=tick_labels, align='center', color='#000000', edgecolor='#000000')
        y_max = ax.get_ylim()[1]

        # Colorize regions and add dividing lines if region_colors present
        previous_day = 0
        for (day, bgcolor) in self.region_colors:
            plt.axvline(x=day, color='#777777', linewidth=0.5)  # draw reference lines
            ax.annotate('{} Days '.format(day), xy=(day - 1, y_max), rotation='vertical', fontsize=7, color='#666666',
                        ha='right', va='top')
            ax.add_patch(
                Rectangle((previous_day, 0), day - previous_day, y_max, facecolor=bgcolor, alpha=0.4, edgecolor=None,
                          zorder=0))
            previous_day = day
        ax.add_patch(Rectangle((previous_day, 0), (self.series.index[-1] - previous_day + self.x_limit_extra), y_max,
                               facecolor='#000000', alpha=0.4, edgecolor=None, zorder=0))

        tick_interval = len(self.series) / (self.x_major_tick_count - 1)
        for i, tick in enumerate(ax.xaxis.get_major_ticks()):
            if i % tick_interval:
                tick.set_visible(False)
            else:
                tick.set_visible(True)
                tick.set_label('{}'.format(self.series.index[i]))

        if self.final_bucket_accumulate:
            tick.set_visible(True)  # Show final tick (just in case it isn't already visible)

        ax.tick_params(direction='out')  # put ticks on the outside of the axes
        ax.yaxis.grid(True)
        ax.yaxis.tick_left()  # ticks only on left
        ax.yaxis.set_visible(True)
        ax.xaxis.tick_bottom()  # ticks only on bottom
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        fig.set_tight_layout(True)
        plt.savefig(filename + '.pdf')
        plt.close()


class MyPie(object):
    def __init__(self, data, labels, explode=None, showValue=False):
        self.data = data
        self.labels = wrapLabels(labels, 20)
        self.explode = explode
        self.showValue = showValue

    def left_right(self, trips):
        lefts = []
        rights = []
        for inner, outer, wedge in trips:
            (x, y) = outer.get_position()
            if x <= 0:
                lefts.append((inner, outer, wedge))
            else:
                rights.append((inner, outer, wedge))
        return lefts, rights

    def too_close(self, trips):
        if len(trips) <= 1:
            return False
        for (inner, outer, wedge) in trips:
            if wedge.theta2 - wedge.theta1 < TOO_SMALL_WEDGE:
                return True
        return False

    def wedge_edge(self, wedge):
        theta = np.pi * (wedge.theta1 + wedge.theta2) / 180
        wedge_x, wedge_y = wedge.center
        x = wedge_x + wedge.r * np.cos(theta / 2.0)
        y = wedge_y + wedge.r * np.sin(theta / 2.0)
        return (x, y)

    def layout_labels(self, trips, ax, right_side=True):
        bottom, top = ax.get_ylim()
        left, right = ax.get_xlim()
        if right_side:
            new_ys = np.linspace(bottom * 0.8, top, len(trips))  # distribute
        else:
            new_ys = np.linspace(top, bottom * 0.8, len(trips))  # distribute

        trips.sort(key=lambda x: self.wedge_edge(x[2])[1], reverse=not right_side)  # sort by wedge_edge y

        for (inner, outer, wedge), y in zip(trips, new_ys):
            outer.set_visible(False)  # hide the old label
            if wedge.theta2 - wedge.theta1 > TOO_SMALL_WEDGE:
                new_text = outer.get_text()  # transfer old label text
            else:
                new_text = '%s\n(%s)' % (outer.get_text(), inner.get_text())
                inner.set_visible(False)  # too small to show inner label, add to outer

            # create annotation from pos to wedge
            xy = self.wedge_edge(wedge)
            if right_side:
                ax.annotate(new_text, xy=xy, xycoords='data',
                            xytext=(right * 1.8, y), textcoords='data',
                            size=6, va='top', ha='right',
                            arrowprops=dict(arrowstyle="-", mutation_scale=30,
                                            connectionstyle="arc3"),
                            )
            else:
                ax.annotate(new_text, xy=xy, xycoords='data',
                            xytext=(left * 1.8, y), textcoords='data',
                            size=6, va='top', ha='left',
                            arrowprops=dict(arrowstyle="-", mutation_scale=30,
                                            connectionstyle="arc3"),
                            )

    def plot(self, filename, size=1.0):
        (w, h) = plt.rcParams['figure.figsize']
        fig = plt.figure(1)
        fig.set_size_inches(fig.get_size_inches() * size)
        ax = fig.add_subplot(1, 1, 1)
        fig.subplots_adjust(left=0.25, right=0.75)

        wedges, outer_labels, inner_labels = plt.pie(self.data, colors=PIE_COLORS,
                                                     explode=self.explode, labels=self.labels,
                                                     labeldistance=1.15, autopct='', pctdistance=0.65, shadow=False)
        for wedge in wedges:
            wedge.set_edgecolor('white')
        i = 0
        total = sum(self.data)
        for label in inner_labels:
            label.set_fontsize(16.0 * size)  # inner value label size
            label.set_color('white')
            if self.showValue:
                label.set_text('{0}, {1:.0f}%'.format(self.data[i], float(self.data[i]) / total * 100.0))
            else:
                label.set_text('%1.1f%%' % (self.data[i]))
            i += 1

        for label in outer_labels:
            label.set_fontsize(8.0 * (1 + size) / 2)

        trips = zip(inner_labels, outer_labels, wedges)

        lefts, rights = self.left_right(trips)
        if self.too_close(lefts):
            self.layout_labels(lefts, ax, False)
        if self.too_close(rights):
            self.layout_labels(rights, ax, True)

        plt.savefig(filename + '.pdf')
        plt.close()


class MyColorBar(object):
    def __init__(self, agencyName, agencyScore, federalScore, label='Average'):
        self.agencyName = agencyName
        self.agencyScore = agencyScore
        self.federalScore = federalScore
        self.label = label

    def plot(self, filename, size=1.0):
        cmap = mpl.cm.RdYlGn_r
        norm = mpl.colors.Normalize(vmin=0, vmax=10)
        fig = plt.figure(figsize=(8, 2))
        fig.set_size_inches(fig.get_size_inches() * size)
        plt.axis('off')

        ax2 = fig.add_axes([0.05, 0.25, 0.9, 0.15])
        cb1 = mpl.colorbar.ColorbarBase(ax2, cmap=cmap,
                                        norm=norm,
                                        orientation='horizontal')
        cb1.set_label('CVSS Score')
        cb1.outline.set_visible(False)
        ax2.xaxis.tick_bottom()

        if (self.agencyScore <= self.federalScore):
            agencyTextXY = (0.25, 0.66)
            federalTextXY = (0.75, 0.66)
        else:
            agencyTextXY = (0.75, 0.66)
            federalTextXY = (0.25, 0.66)

        agencyLabel = '%s %s\n%1.2f' % (self.agencyName, self.label, self.agencyScore)
        federalLabel = 'Federal %s\n%1.2f' % (self.label, self.federalScore)

        ax2.annotate(agencyLabel, xy=(self.agencyScore / 10, 1), xycoords='data',
                     xytext=agencyTextXY, textcoords='figure fraction',
                     size=14, ha='center',
                     bbox=dict(boxstyle="round", fc="1.0", alpha=0.9),
                     arrowprops=dict(arrowstyle="fancy", mutation_scale=30,
                                     fc="0.1", ec="none",
                                     patchB=ax2,
                                     connectionstyle="angle3,angleA=0,angleB=-90"),
                     )

        ax2.annotate(federalLabel, xy=(self.federalScore / 10, 1), xycoords='data',
                     xytext=federalTextXY, textcoords='figure fraction',
                     size=14, ha='center',
                     bbox=dict(boxstyle="round", fc="1.0", alpha=0.9),
                     arrowprops=dict(arrowstyle="fancy", mutation_scale=30,
                                     fc="0.4", ec="none",
                                     patchB=ax2,
                                     connectionstyle="angle3,angleA=0,angleB=-90"),
                     )
        fig.set_tight_layout(True)
        plt.savefig(filename + '.pdf')
        plt.close()


class MyMap(object):
    def __init__(self, coordinates):
        self.coordinates = coordinates
        self.ll_lon = None
        self.ll_lat = None
        self.ur_lon = None
        self.ur_lat = None
        self.__calculate_zoom()

    def __calculate_zoom(self):
        USA_LL = (-126.00, 25.00)
        USA_UR = (-66, 49.50)
        ll_lon, ll_lat = USA_LL
        ur_lon, ur_lat = USA_UR
        for lon, lat in self.coordinates:
            if lon == None or lat == None:
                print('bad value for lon,lat:', lon, lat)
                continue
            if lon < ll_lon:
                ll_lon = lon - 1
            elif lon > ur_lon:
                ur_lon = lon + 1
            if lat < ll_lat:
                ll_lat = lat - 1
            elif lat > ur_lat:
                ur_lat = lat + 1
        self.ll_lon, self.ll_lat, self.ur_lon, self.ur_lat = ll_lon, ll_lat, ur_lon, ur_lat

    def plot(self, filename, size=1.0):
        fig = plt.figure(1)
        fig.set_size_inches(fig.get_size_inches() * size)
        mapp = Basemap(projection='merc',
                       resolution='l',  # area_thresh = 0.1,
                       llcrnrlon=self.ll_lon, llcrnrlat=self.ll_lat,
                       urcrnrlon=self.ur_lon, urcrnrlat=self.ur_lat)
        mapp.drawcoastlines(linewidth=1, color='white')
        mapp.drawcountries(linewidth=1, color='white')
        mapp.drawstates(linewidth=1, color='white')
        mapp.fillcontinents(color=DARK_BLUE)
        mapp.drawmapboundary()
        for lon, lat in self.coordinates:
            if lon == None or lat == None:
                continue
            x, y = mapp(lon, lat)
            mapp.plot(x, y, 'r.', markersize=9)
        fig.set_tight_layout(True)
        plt.savefig(filename + '.pdf')
        plt.close()


class MyLine(object):
    def __init__(self, data_frame, linecolors, yscale='linear', xlabel=None, ylabel=None):
        self.df = data_frame
        self.linecolors = linecolors
        self.yscale = yscale
        self.xlabel = xlabel
        self.ylabel = ylabel

    def plot(self, filename, size=1.0, figsize=None):
        if figsize:
            fig = plt.figure(figsize=figsize)
        else:
            fig = plt.figure(1)
        fig.set_size_inches(fig.get_size_inches() * size)
        ax = fig.add_subplot(1, 1, 1)
        ax.set_yscale(self.yscale)
        if self.xlabel:
            ax.set_xlabel(self.xlabel)
        if self.ylabel:
            ax.set_ylabel(self.ylabel)
        colors = (c for c in self.linecolors)
        for col in self.df.columns:
            series = self.df[col]
            series.plot(style='.-', color=colors.next(), linewidth=2, markersize=10)
        leg = plt.legend(fancybox=True, loc='best')
        # set the alpha value of the legend: it will be translucent
        leg.get_frame().set_alpha(0.5)
        ax.set_ylim(ymin=0)  # Force y-axis to go to 0 (must be done after plot)
        fig.set_tight_layout(True)
        plt.savefig(filename + '.pdf')
        plt.close()


class MyPentaLine(object):
    def __init__(self, data_frame):
        self.df = data_frame

    def plot_four(self, axis, column, color1, color2, last=False, tick_right=False):
        axis.text(0.025, 0.75, column.title(), fontsize='small',
                  horizontalalignment='left',
                  transform=axis.transAxes)
        yloc = plt.MaxNLocator(4, integer=True)
        axis.yaxis.set_major_locator(yloc)
        if tick_right:
            axis.yaxis.tick_right()
        for prefix, style in [('', 'solid'), ('world_', 'dotted')]:
            for col, color in [('host_count', color1), ('vulnerable_host_count', color2)]:
                df = self.df[prefix + column] * 1.0 / self.df[prefix + col]
                df = df.fillna(0)
                df.plot(ax=axis, label=prefix + column, grid=False, color=color, linewidth=2, linestyle=style,
                        marker='.', markersize=10)

        if not last:
            # axis.tick_params(axis='x', labelcolor='white') #nope
            # axis.xaxis.set_ticklabels([]) #nope
            axis.xaxis.set_visible(False)  # kinda: lost upper ticks

    def plot(self, filename, size=1.0):
        df = self.df
        # Three subplots sharing both x/y axes
        fig, axes = plt.subplots(nrows=5, ncols=1, sharex=True, sharey=True)
        fig.set_size_inches(fig.get_size_inches() * size)

        self.plot_four(axes[0], 'total', LIGHT_GREEN, DARK_GREEN)
        self.plot_four(axes[1], 'critical', LIGHT_RED, DARK_RED, tick_right=True)
        self.plot_four(axes[2], 'high', LIGHT_ORANGE, DARK_ORANGE)
        self.plot_four(axes[3], 'medium', LIGHT_YELLOW, DARK_YELLOW, tick_right=True)
        self.plot_four(axes[4], 'low', LIGHT_BLUE, DARK_BLUE, last=True)

        # fig.subplots_adjust(bottom=0.20)

        # build a generic legend to represent all the subplots
        dark_solid_line = plt.Line2D((0, 1), (0, 0), marker='.', color=GREY_DARK)
        light_solid_line = plt.Line2D((0, 1), (0, 0), marker='.', color=GREY_MID)
        dark_dotted_line = plt.Line2D((0, 1), (0, 0), marker='.', linestyle='dotted', color=GREY_DARK)
        light_dotted_line = plt.Line2D((0, 1), (0, 0), marker='.', linestyle='dotted', color=GREY_MID)
        fig.legend([dark_solid_line, light_solid_line, dark_dotted_line, light_dotted_line],
                   ['Vulnerable Hosts', 'All Hosts', 'CH Vulnerable Hosts', 'CH All Hosts'],
                   'lower center', ncol=4, fontsize='x-small')
        # Fine-tune figure; make subplots close to each other
        plt.grid(False)
        # fig.set_tight_layout(True)
        # following line doesn't work with fig.set_tight_layout
        # it does work with plt.tight_layout(), but generates a warning
        fig.subplots_adjust(hspace=0)
        plt.savefig(filename + '.pdf', bbox_inches='tight', pad_inches=0.25)
        plt.close()


class MyStackedLine(object):
    def __init__(self, data_frame, yscale='linear', xlabel=None, ylabel=None, data_labels=None, data_fill_colors=None):
        self.df = data_frame
        self.yscale = yscale
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.data_labels = data_labels
        self.data_fill_colors = data_fill_colors

    def plot(self, filename, size=1.0):
        # TODO Interpolate this data to get a nicer curve
        df = self.df
        fig, axes = plt.subplots(figsize=(8, 2.75))
        fig.set_size_inches(fig.get_size_inches() * size)
        axes.stackplot(df.index, df['young'].values.astype(np.int), df['old'].values.astype(np.int),
                       labels=self.data_labels, colors=self.data_fill_colors, alpha=0.2)
        # axes.locator_params(axis='x', nbins=8, tight=True)       # Limit x-axis to 8 ticks; doesn't seem to work with Date data :(
        axes.yaxis.tick_left()  # ticks only on left
        axes.yaxis.grid(True)
        axes.xaxis.tick_bottom()  # ticks only on bottom
        axes.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
        axes.set_axisbelow(True)
        axes.spines['top'].set_visible(False)
        axes.spines['right'].set_visible(False)
        if self.xlabel:
            plt.xlabel(self.xlabel)
        if self.ylabel:
            plt.ylabel(self.ylabel)
        leg = plt.legend(fancybox=True, loc='lower center', ncol=2, prop={'size': 6}, bbox_to_anchor=(0.5, 1.0))
        leg.get_frame().set_alpha(0.5)  # set the alpha value of the legend: it will be translucent
        for i, tick in enumerate(axes.xaxis.get_major_ticks()):
            tick.label.set_fontsize(6)
        fig.set_tight_layout(True)
        plt.savefig(filename + '.pdf')
        plt.close()


class Boxes(object):
    def __init__(self, dataframe, min_cols=25, other_color='green'):
        self.df = dataframe
        self.min_cols = min_cols
        self.cols = None
        self.other_color = other_color

    def _calculate_cols(self, fig):
        w, h = fig.get_size_inches()
        fig_area = w * h
        data_size = self.df.sum().sum()
        cell_area = fig_area / data_size
        cell_size_in = math.sqrt(cell_area)
        self.cols = max(self.min_cols, math.ceil(w / cell_size_in) + 1)

    def plot(self, filename, size=1.0):
        fig = plt.figure(1)
        fig.set_size_inches(fig.get_size_inches() * size)
        self._calculate_cols(fig)

        i, j = fig.get_size_inches()
        aspect_ratio = i / j
        width = 1.0 / self.cols
        height = width * aspect_ratio

        ax = fig.add_subplot(1, 1, 1)
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)

        boxes = []
        facecolors = []
        colors_wo_green = COLORS[0:4][::-1]
        color_iter = iter(colors_wo_green)
        i = 0
        j = 1
        for tup in self.df.itertuples():
            tup = list(tup)
            index = tup.pop(0)  # pop off index, unused
            color = color_iter.next()
            for tup_i, count in enumerate(tup):  # iterate remainding values of row
                for k in range(count):
                    center = [i * width + (width / 2), 1 - (j * height - (height / 2))]
                    bottom_left = [i * width, 1 - (j * height)]
                    r = Rectangle(bottom_left, width, height)
                    boxes.append(r)
                    facecolors.append(color)
                    if tup_i > 0:
                        r = Ellipse(center, width / 2, height / 2)
                        boxes.append(r)
                        facecolors.append(self.other_color)
                        # r = CirclePolygon(center, radius= width/2 ,resolution=8)
                        # r = RegularPolygon(center, 4, radius=height/2, orientation=0)
                    i += 1
                    if i >= self.cols:
                        i = 0
                        j += 1

        patches = PatchCollection(boxes, facecolors=facecolors, edgecolors='white')
        ax.add_collection(patches)
        fig.set_tight_layout(True)
        plt.savefig(filename + '.pdf')
        plt.close()
        return self.cols


class Histogram(object):
    def __init__(self, bin_counts, highlight_bin):
        self.bin_counts = bin_counts
        self.highlight_bin = highlight_bin

    def plot(self, filename, size=1.0):
        fig = plt.figure(1)
        fig.set_size_inches(fig.get_size_inches() * size)

        ax = fig.add_subplot(1, 1, 1)

        pos = np.arange(len(self.bin_counts))  # the bar centers on the x axis
        colors = [GREY_LIGHT] * len(self.bin_counts)
        highlight_colors = [GREEN, GREEN, BLUE, BLUE, YELLOW, YELLOW, ORANGE, ORANGE, RED, RED]
        colors[self.highlight_bin] = highlight_colors[self.highlight_bin]
        rects = plt.bar(pos, self.bin_counts, align='edge',
                        color=colors, edgecolor='white', linewidth=1, width=1)

        ax.yaxis.grid(False)
        # ax.spines['left'].set_visible(False)
        # ax.spines['top'].set_visible(False)
        # ax.spines['right'].set_visible(False)
        ax.yaxis.set_visible(False)
        # ax.xaxis.set_visible(False)
        ax.set_frame_on(False)
        ax.tick_params(top='off', bottom='off')
        ax.set_xlim(0, len(self.bin_counts))
        ax.xaxis.label.set_fontsize(18)
        ax.set_xlabel('CVSS')
        tick_colors = [GREEN, BLUE, YELLOW, ORANGE, RED, RED]
        tick_count = len(ax.xaxis.get_major_ticks())
        for i, tick in enumerate(ax.xaxis.get_major_ticks()):
            tick.label.set_fontsize(18)
            tick.label.set_color(tick_colors[i])
            # if i == 0:
            #     tick.label.set_color(GREEN)
            # elif i == tick_count - 1:
            #     tick.label.set_color(RED)
            # else: # hide everything but ends
            #     tick.label.set_visible(False)

        fig.set_tight_layout(True)
        plt.savefig(filename + '.pdf')
        plt.close()


class Histogram2(object):
    def __init__(self, histogram_data, bar_colors, tick_colors, x_label=None, y_label=None):
        self.histogram_data = histogram_data
        self.bar_colors = bar_colors
        self.tick_colors = tick_colors
        self.x_label = x_label
        self.y_label = y_label

    def plot(self, filename, size=1.0):
        fig = plt.figure(figsize=(8, 2.5))
        fig.set_size_inches(fig.get_size_inches() * size)

        ax = fig.add_subplot(1, 1, 1)
        rects = plt.bar(self.histogram_data[1][:-1], self.histogram_data[0], align='edge',
                        color=self.bar_colors, edgecolor='white', linewidth=1, width=0.5)

        # ax.set_frame_on(False)
        plt.xticks(self.histogram_data[1])  # Put a tick at edge of each bucket
        ax.tick_params(top='off', bottom='off')
        ax.yaxis.tick_left()  # ticks only on left
        ax.yaxis.grid(True)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        # ax.spines['bottom'].set_visible(False)
        ax.xaxis.label.set_fontsize(10)
        if self.x_label:
            ax.set_xlabel(self.x_label)
        if self.y_label:
            ax.set_ylabel(self.y_label)
        ax.set_xlim(min(self.histogram_data[1]), max(self.histogram_data[1]))

        for i, tick in enumerate(ax.xaxis.get_major_ticks()):
            # if i % 2:     # show every other label
            #     tick.label.set_visible(False)
            tick.label.set_fontsize(10)
            tick.label.set_color(self.tick_colors[i])

        fig.set_tight_layout(True)
        plt.savefig(filename + '.pdf')
        plt.close()


class MyTrustyBar(object):
    def __init__(self, percentage_list, label_list, fill_color, title=None):
        self.title = title
        self.percentage_list = percentage_list
        self.label_list = label_list
        self.fill_color = fill_color

    def plot(self, filename):
        x_left_indices = np.arange(len(self.percentage_list))    # the x locations for the groups
        width = 0.5       # the width of the bars: can also be len(x) sequence

        p1 = plt.bar(x_left_indices, self.percentage_list, width, color=self.fill_color, edgecolor='none')
        p2 = plt.bar(x_left_indices, [100-x for x in self.percentage_list], width, color='w', bottom=self.percentage_list, edgecolor='none')

        plt.ylabel('Percent (%)', fontsize=14, style='italic')
        if self.title:
            plt.title(self.title, fontsize=20, fontweight='bold', y=1.07)
        plt.xticks(x_left_indices, self.label_list, fontsize=14, style='italic')
        plt.yticks(np.arange(10, 100, 10), fontsize=13)

        for bar in p1:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, 1.0*height,
                        '%d' % int(round(height,0)) +'%', ha='center', va='bottom', fontsize=15)

        #plt.show()
        plt.savefig(filename + '.pdf')#, bbox_inches=0, pad_inches=0
        plt.close()


class MyDonutPie(object):
    def __init__(self, percentage_full, label, fill_color):
        self.percentage_full = percentage_full
        self.label = label
        self.fill_color = fill_color

    def plot(self, filename, size=1.0):
        # Override default figsize (make square), then scale by size parameter
        fig_width = fig_height = 4.0 * size
        plt.rcParams.update({'figure.figsize':[fig_width, fig_height]})
        extent = mpl.transforms.Bbox(((0, 0), (fig_width, fig_height)))  # Minimize whitespace around chart

        labels = '', ''
        sizes = [100 - self.percentage_full, self.percentage_full]
        colors = ['white', self.fill_color]

        # Set edge color to black
        # See https://matplotlib.org/users/dflt_style_changes.html#patch-edges-and-color
        plt.rcParams['patch.force_edgecolor'] = True
        plt.rcParams['patch.facecolor'] = 'b'

        plt.pie(sizes, labels=labels, colors=colors, shadow=False, startangle=90) #autopct='%1.1f%%'

        # Draw a circle at the center of pie to make it look like a donut
        centre_circle = plt.Circle((0,0),0.75,color='black', fc='white',linewidth=1.25)
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)

        plt.text(0, 0.15, str(self.percentage_full) + '%', horizontalalignment='center', verticalalignment='center', fontsize=50)
        plt.text(0, -0.2, self.label, horizontalalignment='center', verticalalignment='center', fontsize=19.5, fontweight='bold')
        plt.tight_layout(pad=0.0, w_pad=0.0, h_pad=0.0)
        # plt.tight_layout(pad=0.4, w_pad=0.5, h_pad=1.0)

        # Set aspect ratio to be equal so that pie is drawn as a circle.
        plt.axis('equal')
        # plt.show()
        plt.savefig(filename + '.pdf', bbox_inches=extent, pad_inches=0)
        # plt.savefig('overall-compliance')
        plt.close()


if __name__ == "__main__":
    setup()

    m = MyMessage('Figure Omitted\nNo Vulnerabilities Detected')
    m.plot('message')
